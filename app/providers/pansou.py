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

    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        tasks = []

        # ① 自建 pansou-edge（若已配置）
        if config.PANSOU_EDGE_URL:
            tasks.append(self._search_self_hosted(keyword))

        # ② 内置公开节点兜底
        tasks.append(self._search_public_nodes(keyword))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_links: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                all_links.extend(r)

        if not all_links:
            return []

        # 按 URL 去重
        seen = set()
        unique: List[Dict[str, Any]] = []
        for item in all_links:
            u = item.get("url", "")
            if u and u not in seen:
                seen.add(u)
                unique.append(item)

        # PanCheck 有效性过滤
        # 关键：给过滤加独立预算，超时则回退为「不过滤」，绝不因过滤慢而丢掉全部结果
        budget = max(1.5, config.PANCHECK_TIMEOUT * 2)
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
        调用自建的 pansou-edge 节点。
        多个候选接口「并行竞速」，谁先返回有效数据就用谁，避免串行等待拖慢整体。
        """
        base = config.PANSOU_EDGE_URL
        headers = {"Accept": "application/json", "User-Agent": "FastBox/1.0"}
        if config.PANSOU_EDGE_TOKEN:
            headers["Authorization"] = f"Bearer {config.PANSOU_EDGE_TOKEN}"

        endpoints = [
            (f"{base}/api/search", {"kw": keyword, "res": "all", "page": 1}),
            (f"{base}/api/search", {"q": keyword, "res": "all"}),
            (f"{base}/search",     {"kw": keyword}),
            (f"{base}/api/pan/search", {"keyword": keyword}),
        ]

        timeout = httpx.Timeout(config.PANSOU_EDGE_TIMEOUT, connect=2.0)

        async def probe(client, url, params):
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            return self._parse_pansou_response(resp.json(), keyword)

        async with httpx.AsyncClient(timeout=timeout, verify=False,
                                     follow_redirects=True, headers=headers) as client:
            tasks = [asyncio.create_task(probe(client, u, p)) for u, p in endpoints]
            done, pending = await asyncio.wait(
                tasks, timeout=config.PANSOU_EDGE_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            for t in done:
                try:
                    r = t.result()
                    if r:
                        return r
                except Exception:
                    continue

        return []

    @staticmethod
    def _parse_pansou_response(data: Any, keyword: str) -> List[Dict[str, Any]]:
        """解析 pansou / pansou-edge 的返回结构"""
        links: List[Dict[str, Any]] = []
        if not isinstance(data, dict):
            return links

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
            "xunlei": [], "115": [], "123": [], "tianyi": [], "magnet": [], "other": [],
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
