import asyncio
import re
import time
from typing import List, Dict, Any, Tuple
from app.config import config
from app.core.cache import search_cache
from app.providers.collectors import COLLECTOR_STATIONS, CollectorProvider
from app.providers.pansou import PanSouEdgeProvider

# 网盘线路标题形如「【夸克4K原盘】繁花」，前缀是网盘来源名
_PAN_TITLE_PREFIX = re.compile(r"^【[^】]*】\s*")


class Aggregator:
    """
    极速多源并发聚合引擎

    性能保障三道防线：
      ① 单源超时   —— 每个 provider 内部有 httpx timeout
      ② 全局截止   —— asyncio.wait + timeout，到点即取已完成的结果（不等待慢源）
      ③ 双层缓存   —— 命中缓存直接毫秒返回
    """

    def __init__(self):
        self.providers = []
        for item in COLLECTOR_STATIONS:
            self.providers.append(
                CollectorProvider(name=item["name"], api_url=item["api"],
                                  timeout=config.SEARCH_TIMEOUT)
            )
        self.providers.append(PanSouEdgeProvider(timeout=config.SEARCH_TIMEOUT))

    # ------------------------------------------------------------------
    @property
    def deadline(self) -> float:
        """
        全局搜索截止时间（秒）。
        比单源超时略大，保证「快源先返回、慢源直接丢弃」。
        """
        return max(1.0, config.SEARCH_TIMEOUT + 0.8)

    # ------------------------------------------------------------------
    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        cache_key = f"search:{keyword}"
        cached = search_cache.get(cache_key)
        if cached is not None:
            return cached

        start = time.time()

        # ---- ① 并发调度全部数据源 ----
        tasks = []
        for p in self.providers:
            if not getattr(p, "enabled", True):
                continue
            # 每个源再包一层独立超时，双保险
            tasks.append(asyncio.create_task(
                asyncio.wait_for(p.search(keyword), timeout=self.deadline + 0.5)
            ))

        raw_items: List[Dict[str, Any]] = []
        truncated = False
        if tasks:
            # ---- ② 全局截止：到点即收，不等慢源 ----
            done, pending = await asyncio.wait(tasks, timeout=self.deadline)

            # 仍有未完成的源 → 本次结果是「截断」的（可能缺少网盘等慢源数据）
            truncated = bool(pending)

            for t in pending:
                t.cancel()
            if pending:
                # 回收被取消的任务，避免 "Task exception was never retrieved"
                await asyncio.gather(*pending, return_exceptions=True)

            for t in done:
                try:
                    r = t.result()
                    if isinstance(r, list):
                        raw_items.extend(r)
                except Exception:
                    continue

        # ---- ③ 合并去重 ----
        merged = self._merge_results(keyword, raw_items)

        cost_ms = round((time.time() - start) * 1000, 2)
        print(f"[Aggregator] '{keyword}' -> {len(merged)} 部影视, "
              f"{len(raw_items)} 条线路, 耗时 {cost_ms}ms "
              f"(截止 {self.deadline}s, 源 {len(tasks)} 个"
              f"{', 结果截断' if truncated else ''})")

        # 缓存策略：
        #   完整结果 → 正常 TTL 长期缓存
        #   截断结果 → 只做极短缓存，避免一次网络抖动在缓存有效期内持续返回残缺数据
        #              （曾出现：某次搜索因熔断只拿到 3 个源，该残缺结果被缓存 30 分钟，
        #                导致同一关键词后续请求一直缺网盘线路）
        if truncated:
            search_cache.set(cache_key, merged, ttl=config.CACHE_TTL_TRUNCATED)
        else:
            search_cache.set(cache_key, merged, ttl=config.CACHE_TTL_SEARCH)
        return merged

    # ------------------------------------------------------------------
    @staticmethod
    def _clean_title(title: str) -> str:
        return (title.replace("【", "").replace("】", "")
                     .replace("（", "").replace("）", "").strip())

    @staticmethod
    def _pan_keyword(title: str) -> str:
        """从「【夸克4K原盘】繁花」里取出「繁花」"""
        return _PAN_TITLE_PREFIX.sub("", (title or "").strip()).strip()

    def _merge_results(self, keyword: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按影视标题聚合线路：一个影片一张卡片，内部含多条播放线路

        网盘结果（type == "pan"）会**优先并入同名的影视卡片**，成为该影片的额外线路，
        这样用户在 TVBox 里点开《繁花》就能同时看到「切片秒播」和「夸克/阿里网盘」两类线路，
        不必在几十条搜索结果里翻找网盘专属卡片。
        若没有同名影视卡片（例如只有网盘有这部片），才单独成条。
        """
        grouped: Dict[str, Dict[str, Any]] = {}
        pan_items: List[Dict[str, Any]] = []

        # ---- ① 先聚合切片站结果 ----
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            if item.get("type") == "pan":
                pan_items.append(item)
                continue

            clean = self._clean_title(title)
            if clean not in grouped:
                grouped[clean] = {
                    "vod_id": item.get("vod_id"),
                    "vod_name": title,
                    "vod_pic": item.get("poster", ""),
                    "vod_remarks": item.get("remarks", ""),
                    "vod_year": item.get("year", ""),
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": item.get("desc", ""),
                    "sources": [],
                }
            grouped[clean]["sources"].append({
                "source_name": item.get("source"),
                "episodes": item.get("episodes", []),
            })

        # ---- ② 网盘结果：能对上同名影视就并入，否则独立成条 ----
        pan_ep_total: Dict[str, int] = {}   # clean_key -> 并入的网盘资源总数

        for item in pan_items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            pan_kw = self._pan_keyword(title)
            clean_kw = self._clean_title(pan_kw)
            target = grouped.get(clean_kw)

            if target is not None:
                # 并入主卡片，成为一条额外线路
                target["sources"].append({
                    "source_name": item.get("source"),
                    "episodes": item.get("episodes", []),
                })
                pan_ep_total[clean_kw] = (
                    pan_ep_total.get(clean_kw, 0) + len(item.get("episodes") or [])
                )
                continue

            # 没有同名影视 → 保持独立卡片
            key = f"__pan__{title}"
            grouped[key] = {
                "vod_id": item.get("vod_id"),
                "vod_name": title,
                "vod_pic": item.get("poster", ""),
                "vod_remarks": item.get("remarks", "网盘资源"),
                "vod_year": item.get("year", ""),
                "vod_actor": "",
                "vod_director": "",
                "vod_content": f"由 {item.get('source')} 提供的网盘资源",
                "sources": [{
                    "source_name": item.get("source"),
                    "episodes": item.get("episodes", []),
                }],
            }

        # 统一回写「含 N 个网盘资源」备注，方便用户一眼看出哪部片有网盘线路
        for clean_kw, n in pan_ep_total.items():
            g = grouped.get(clean_kw)
            if g is None or n <= 0:
                continue
            base = str(g.get("vod_remarks") or "").strip()
            g["vod_remarks"] = f"{base} · 含{n}个网盘资源" if base else f"含{n}个网盘资源"

        res = list(grouped.values())

        def sort_key(x: Dict[str, Any]) -> Tuple[int, int]:
            name = x["vod_name"]
            # 完全匹配 > 包含关键词 > 其他
            if name == keyword:
                rank = 0
            elif keyword in name:
                rank = 1
            else:
                rank = 2
            # 线路越多越靠前
            return (rank, -len(x.get("sources", [])))

        res.sort(key=sort_key)
        return res

    # ------------------------------------------------------------------
    def format_to_vod_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """转为 TVBox / MacCMS 详情格式"""
        play_from_list = []
        play_url_list = []

        for s in item.get("sources", []):
            play_from_list.append(s.get("source_name", "默认线路"))
            eps = s.get("episodes", []) or []
            play_url_list.append("#".join(f"{e.get('name')}${e.get('url')}" for e in eps))

        return {
            "vod_id": item.get("vod_id"),
            "vod_name": item.get("vod_name"),
            "vod_pic": item.get("vod_pic", ""),
            "vod_remarks": item.get("vod_remarks", ""),
            "vod_year": item.get("vod_year", ""),
            "vod_content": item.get("vod_content", ""),
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }


aggregator = Aggregator()
