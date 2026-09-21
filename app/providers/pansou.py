import asyncio
import httpx
from typing import List, Dict, Any
from urllib.parse import quote
from app.providers.base import BaseProvider
from app.core.pan_check import PanCheck
from app.config import config


class PanSouEdgeProvider(BaseProvider):
    """
    网盘多源聚合搜索服务

    优先级：
      1. 若配置了 PANSOU_EDGE_URL（自建 pansou-edge），优先走自建节点，速度快、无频率限制
      2. 同时并发内置的公开盘搜节点作为兜底，保证资源覆盖面

    搜索到的网盘链接会交给 PanCheck 做有效性过滤（remote 或 local 模式）
    """

    def __init__(self, timeout: float = 3.5):
        super().__init__(name="全网盘搜聚合", enabled=config.ENABLE_PANSOU_EDGE, timeout=timeout)

    # 自建节点独占等待窗口（秒）。
    # 自建 pansou-edge 正常 <900ms；若超过这个窗口说明它异常，转公开节点兜底。
    # 注意：窗口耗尽后 self_task 不会被丢弃，仍会参与第 ③ 步的兜底竞速。
    _SELF_HOSTED_WAIT = 1.5

    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        all_links: List[Dict[str, Any]] = []
        self_task = None
        public_task = asyncio.create_task(self._search_public_nodes(keyword))

        # ① 自建 pansou-edge 优先：它快且稳定，先给它一个独占窗口。
        #    注意 asyncio.wait 在任务完成时立即返回，不会傻等满窗口。
        if config.PANSOU_EDGE_URLS:
            self_task = asyncio.create_task(self._search_self_hosted(keyword))
            done, _ = await asyncio.wait({self_task}, timeout=self._SELF_HOSTED_WAIT)
            for t in done:
                try:
                    r = t.result()
                    if isinstance(r, list):
                        all_links.extend(r)
                except Exception:
                    pass

        # ② 自建节点已有结果 → 立刻收工，绝不等慢的公开节点。
        #    这是关键：公开节点单次可达 4s+，若等它会被全局截止熔断一起取消，
        #    导致已经到手的自建节点结果全部白丢。
        if all_links:
            await self._cancel_tasks(self_task, public_task)
            return await self._finalize(keyword, all_links)

        # ③ 自建节点没在窗口内出结果 → 再给「自建 + 公开」一个短兜底预算。
        #    注意这里把 self_task 也一起等：它可能只是慢了一点点，
        #    直接取消掉太浪费；两个都等，谁先出结果就用谁。
        fallback = {t for t in (self_task, public_task) if t is not None}
        done, pending = await asyncio.wait(
            fallback, timeout=max(1.0, config.SEARCH_TIMEOUT * 0.5)
        )
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for t in done:
            try:
                r = t.result()
                if isinstance(r, list):
                    all_links.extend(r)
            except Exception:
                pass

        if not all_links:
            return []

        return await self._finalize(keyword, all_links)

    @staticmethod
    async def _cancel_tasks(*tasks) -> None:
        """取消未完成的任务并回收，避免留下悬挂协程"""
        alive = [t for t in tasks if t is not None]
        for t in alive:
            if not t.done():
                t.cancel()
        if alive:
            await asyncio.gather(*alive, return_exceptions=True)

    async def _finalize(self, keyword: str, all_links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重 → PanCheck 过滤 → 按网盘类型分组为 TVBox 线路"""
        # 按 URL 去重
        seen = set()
        unique: List[Dict[str, Any]] = []
        for item in all_links:
            u = item.get("url", "")
            if u and u not in seen:
                seen.add(u)
                unique.append(item)

        if not unique:
            return []

        # PanCheck 有效性过滤
        # 关键：给过滤加独立预算，超时则回退为「不过滤」，绝不因过滤慢而丢掉全部结果。
        # 网盘站探活本身较慢（部分站点甚至不可达），预算过大会白等，
        # 因此这里压到 1.2s 以内 —— 换来的是整体响应速度。
        budget = max(0.8, min(config.PANCHECK_TIMEOUT, 1.2))
        try:
            valid_links = await asyncio.wait_for(
                PanCheck.filter_valid_links(unique), timeout=budget
            )
        except asyncio.TimeoutError:
            valid_links = unique
        except Exception:
            valid_links = unique

        if not valid_links:
            return []

        return self._group_by_pan_type(keyword, valid_links)

    # ------------------------------------------------------------------
    # 自建 pansou-edge 适配
    # ------------------------------------------------------------------
    async def _search_self_hosted(self, keyword: str) -> List[Dict[str, Any]]:
        """
        调用自建的 pansou / pansou-edge 节点。

        **支持配置多个候选地址**（PANSOU_EDGE_URL 用逗号分隔）。
        所有地址的所有候选接口「并行竞速」，但**不能只取第一个返回的**：
        某些参数组合（例如带 res=all）会很快返回错误或空结果，
        若直接采用就会把真正有数据的那个候选取消掉。
        因此这里持续等待，直到拿到**非空结果**或整体超时。

        这样即使某个地址写错 / 被墙 / 服务挂了，其他地址仍能兜底，
        不会出现「网盘一条都搜不到」的整段失效。
        """
        bases = config.PANSOU_EDGE_URLS
        if not bases:
            return []

        headers = {"Accept": "application/json", "User-Agent": "FastBox/1.0"}
        if config.PANSOU_EDGE_TOKEN:
            headers["Authorization"] = f"Bearer {config.PANSOU_EDGE_TOKEN}"

        # 顺序即优先级：第一个是实测覆盖面最广的参数组合（纯 q，不加 res）
        endpoints = []
        for base in bases:
            endpoints.extend([
                (f"{base}/api/search", {"q": keyword}),
                (f"{base}/api/search", {"kw": keyword, "res": "all", "page": 1}),
                (f"{base}/api/search", {"q": keyword, "res": "all"}),
                (f"{base}/search",     {"kw": keyword}),
            ])

        timeout = httpx.Timeout(config.PANSOU_EDGE_TIMEOUT, connect=2.0)

        async def probe(client, url, params):
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            try:
                return self._parse_pansou_response(resp.json(), keyword)
            except Exception:
                return []

        async with httpx.AsyncClient(timeout=timeout, verify=False,
                                     follow_redirects=True, headers=headers) as client:
            tasks = [asyncio.create_task(probe(client, u, p)) for u, p in endpoints]
            pending = set(tasks)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + config.PANSOU_EDGE_TIMEOUT

            try:
                while pending:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    done, pending = await asyncio.wait(
                        pending, timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    if not done:
                        break
                    for t in done:
                        try:
                            r = t.result()
                        except Exception:
                            continue
                        if r:
                            return r          # 拿到非空结果 → 立即返回
            finally:
                for t in pending:
                    t.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        # 所有候选地址都没拿到结果 —— 打日志便于排查（是地址写错？还是服务挂了？）
        print(f"[pansou] 自建节点无结果 keyword={keyword!r} "
              f"候选地址={bases} 超时={config.PANSOU_EDGE_TIMEOUT}s")
        return []

    # pansou / pansou-edge 的分类键 → 本项目的内部类型名
    # 注意：pansou 用 "aliyun"，本项目内部统一叫 "ali"
    _PANSOU_TYPE_MAP = {
        "quark": "quark", "aliyun": "ali", "ali": "ali", "alipan": "ali",
        "baidu": "baidu", "uc": "uc", "xunlei": "xunlei", "115": "115",
        "123": "123", "123pan": "123", "tianyi": "tianyi",
        "189": "tianyi", "magnet": "magnet", "ed2k": "magnet",
    }

    @classmethod
    def _parse_merged_by_type(cls, merged: Dict[str, Any], keyword: str) -> List[Dict[str, Any]]:
        """
        解析 pansou 标准返回结构：
            data.merged_by_type = {"quark": [ {url, password, note, datetime, source}, ... ], ...}

        这是 pansou / pansou-edge 最常见也最完整的格式，必须优先识别。
        """
        links: List[Dict[str, Any]] = []
        for type_key, items in merged.items():
            if not isinstance(items, list):
                continue
            mapped = cls._PANSOU_TYPE_MAP.get(str(type_key).strip().lower(), "")
            for it in items:
                if not isinstance(it, dict):
                    continue
                u = it.get("url") or it.get("link") or it.get("share_url") or ""
                if not u:
                    continue
                title = it.get("note") or it.get("title") or it.get("name") or keyword

                ptype = mapped
                if not ptype:
                    # other / mobile 等未知分类：从 URL 反推网盘类型，兜底归入 other
                    found = PanCheck.extract_share_info(u)
                    ptype = found[0]["type"] if found else "other"

                links.append({
                    "type": ptype,
                    "url": u,
                    "pwd": it.get("password") or it.get("pwd") or "",
                    "title": title,
                })
        return links

    @staticmethod
    def _parse_pansou_response(data: Any, keyword: str) -> List[Dict[str, Any]]:
        """解析 pansou / pansou-edge 的返回结构"""
        links: List[Dict[str, Any]] = []
        if not isinstance(data, dict):
            return links

        # ① 优先识别 pansou 标准格式：{"code":0,"data":{"merged_by_type":{...}}}
        #    也兼容 merged_by_type 直接挂在顶层的情况
        scope = data.get("data") if isinstance(data.get("data"), dict) else data
        merged = scope.get("merged_by_type") if isinstance(scope, dict) else None
        if not isinstance(merged, dict):
            merged = data.get("merged_by_type")
        if isinstance(merged, dict) and merged:
            parsed = PanSouEdgeProvider._parse_merged_by_type(merged, keyword)
            if parsed:
                return parsed

        items = None
        for key in ("data", "results", "list", "items"):
            v = data.get(key)
            if isinstance(v, list):
                items = v
                break
            if isinstance(v, dict):
                for k2 in ("list", "items", "results"):
                    if isinstance(v.get(k2), list):
                        items = v[k2]
                        break
                if items:
                    break

        if not items:
            return links

        for it in items:
            if not isinstance(it, dict):
                continue
            title = it.get("title") or it.get("name") or keyword
            # 有些结构把链接放在 links 数组里
            sub_links = it.get("links") or it.get("urls")
            if isinstance(sub_links, list) and sub_links:
                for sl in sub_links:
                    if isinstance(sl, dict):
                        u = sl.get("url") or sl.get("link") or ""
                        ptype = (sl.get("type") or "").lower()
                    else:
                        u, ptype = str(sl), ""
                    if not u:
                        continue
                    if not ptype:
                        found = PanCheck.extract_share_info(u)
                        if found:
                            ptype = found[0]["type"]
                        else:
                            continue
                    links.append({
                        "type": ptype,
                        "url": u,
                        "pwd": sl.get("password", "") if isinstance(sl, dict) else "",
                        "title": title,
                    })
            else:
                raw = f"{it.get('url','')} {it.get('link','')} {it.get('share_url','')} {title}"
                for ex in PanCheck.extract_share_info(raw):
                    ex["title"] = title
                    links.append(ex)

        return links

    # ------------------------------------------------------------------
    # 内置公开节点兜底
    # ------------------------------------------------------------------
    async def _search_public_nodes(self, keyword: str) -> List[Dict[str, Any]]:
        """并发调用内置的公开盘搜节点"""
        nodes = [
            self._node_yisou(keyword),
            self._node_quark(keyword),
            self._node_general(keyword),
        ]
        results = await asyncio.gather(*nodes, return_exceptions=True)

        links: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                links.extend(r)
        return links

    async def _node_yisou(self, keyword: str) -> List[Dict[str, Any]]:
        links = []
        url = f"https://api.yisou.fun/api/search?word={quote(keyword)}&page=1"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    for it in (data.get("data", {}) or {}).get("list", []) or []:
                        raw = f"{it.get('url','')} {it.get('title','')}"
                        for ex in PanCheck.extract_share_info(raw):
                            ex["title"] = it.get("title", keyword)
                            links.append(ex)
        except Exception:
            pass
        return links

    async def _node_quark(self, keyword: str) -> List[Dict[str, Any]]:
        links = []
        url = f"https://pan.quark.cn/api/v1/search/public?kw={quote(keyword)}&page=1&size=10"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    for it in (data.get("data", {}) or {}).get("list", []) or []:
                        s_url = it.get("share_url") or it.get("url") or ""
                        for ex in PanCheck.extract_share_info(s_url):
                            ex["title"] = it.get("title", keyword)
                            links.append(ex)
        except Exception:
            pass
        return links

    async def _node_general(self, keyword: str) -> List[Dict[str, Any]]:
        links = []
        url = f"https://so.25pan.com/api/search?keyword={quote(keyword)}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    for it in data.get("data", []) or []:
                        raw = str(it)
                        for ex in PanCheck.extract_share_info(raw):
                            ex["title"] = it.get("name", keyword)
                            links.append(ex)
        except Exception:
            pass
        return links

    # ------------------------------------------------------------------
    # 结果分组
    # ------------------------------------------------------------------
    @staticmethod
    def _group_by_pan_type(keyword: str, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按网盘类型分组，每组输出一条 TVBox 线路"""
        buckets: Dict[str, List[Dict[str, str]]] = {
            "quark": [], "ali": [], "baidu": [], "uc": [],
            "xunlei": [], "115": [], "123": [], "tianyi": [],
            "guangya": [], "mobile139": [], "magnet": [], "other": [],
        }
        for lk in links:
            ptype = lk.get("type", "other")
            title = lk.get("title", keyword)
            pwd = lk.get("pwd", "")
            name = title + (f" (提取码: {pwd})" if pwd else "")
            buckets.setdefault(ptype, buckets["other"]).append(
                {"name": name, "url": lk.get("url", "")}
            )

        group_meta = [
            ("quark",  "夸克4K原盘", "网盘4K"),
            ("ali",    "阿里高清网盘", "网盘原画"),
            ("baidu",  "百度网盘", "网盘资源"),
            ("uc",     "UC网盘", "网盘资源"),
            ("xunlei", "迅雷网盘", "网盘资源"),
            ("115",    "115网盘", "网盘原盘"),
            ("123",    "123网盘", "网盘资源"),
            ("tianyi", "天翼云盘", "网盘资源"),
            ("guangya", "光雅盘", "网盘资源"),
            ("mobile139", "移动云盘", "网盘资源"),
            ("magnet", "磁力链接", "磁力资源"),
            ("other",  "其他网盘", "网盘资源"),
        ]

        out: List[Dict[str, Any]] = []
        for ptype, source_name, category in group_meta:
            items = buckets.get(ptype) or []
            if not items:
                continue
            out.append({
                "source": source_name,
                "type": "pan",
                "vod_id": f"pan_{ptype}_{quote(keyword)}",
                "title": f"【{source_name}】{keyword}",
                "category": category,
                "remarks": f"共 {len(items)} 个有效资源",
                "episodes": items[:15],
            })
        return out
