import asyncio
import time
from typing import List, Dict, Any, Optional
from app.config import config
from app.core.cache import search_cache
from app.providers.collectors import COLLECTOR_STATIONS, CollectorProvider
from app.providers.pansou import PanSouEdgeProvider

class Aggregator:
    """
    极速多源并发聚合引擎
    并发调度采集站直链源与网盘聚合源，毫秒级熔断合并
    """
    def __init__(self):
        self.providers = []
        # 加载所有切片采集站
        for item in COLLECTOR_STATIONS:
            self.providers.append(
                CollectorProvider(name=item["name"], api_url=item["api"], timeout=config.SEARCH_TIMEOUT)
            )
        # 加载网盘聚合源
        self.providers.append(PanSouEdgeProvider(timeout=config.SEARCH_TIMEOUT + 0.5))

    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        keyword = keyword.strip()
        if not keyword:
            return []

        # 检查缓存
        cached = search_cache.get(f"search:{keyword}")
        if cached is not None:
            return cached

        start_time = time.time()

        # 并发请求全部源
        tasks = [p.search(keyword) for p in self.providers]
        done_results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_items = []
        for r in done_results:
            if isinstance(r, list):
                raw_items.extend(r)

        # 智能整合：同名影视聚合到一起，合并为多条线路
        merged = self._merge_results(keyword, raw_items)

        cost = round((time.time() - start_time) * 1000, 2)
        print(f"[Aggregator] Search '{keyword}' completed in {cost}ms, total results: {len(merged)}")

        # 写入缓存
        search_cache.set(f"search:{keyword}", merged, ttl=config.CACHE_TTL_SEARCH)
        return merged

    def _merge_results(self, keyword: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按影视标题聚合线路：
        一个影片展示为一个卡片，内部包含暴风、量子、红牛、网盘等多条清晰线路
        """
        grouped: Dict[str, Dict[str, Any]] = {}

        for item in items:
            title = item.get("title", "").strip()
            if not title:
                continue

            # 标准化名称对比
            clean_title = title.replace("【", "").replace("】", "").replace("（", "").replace("）", "")
            
            # 如果是网盘专属项，单独保留或并入主卡片
            if item.get("type") == "pan":
                grouped[title] = {
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
                        "episodes": item.get("episodes", [])
                    }]
                }
                continue

            # 采集站影视项
            if clean_title not in grouped:
                grouped[clean_title] = {
                    "vod_id": item.get("vod_id"),
                    "vod_name": title,
                    "vod_pic": item.get("poster", ""),
                    "vod_remarks": item.get("remarks", ""),
                    "vod_year": item.get("year", ""),
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": item.get("desc", ""),
                    "sources": []
                }

            grouped[clean_title]["sources"].append({
                "source_name": item.get("source"),
                "episodes": item.get("episodes", [])
            })

        # 转换为列表，优先展示标题最精确匹配的结果
        res_list = list(grouped.values())
        res_list.sort(key=lambda x: (
            0 if x["vod_name"] == keyword else (1 if keyword in x["vod_name"] else 2),
            -len(x.get("sources", []))
        ))
        return res_list

    def format_to_vod_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """将内部聚合并发结构转为 TVBox 客户端能直接播放的 MacCMS 详情格式"""
        sources = item.get("sources", [])
        
        play_from_list = []
        play_url_list = []

        for s in sources:
            s_name = s.get("source_name", "默认线路")
            play_from_list.append(s_name)
            
            ep_strs = []
            for ep in s.get("episodes", []):
                ep_strs.append(f"{ep.get('name')}${ep.get('url')}")
            play_url_list.append("#".join(ep_strs))

        vod_play_from = "$$$".join(play_from_list)
        vod_play_url = "$$$".join(play_url_list)

        return {
            "vod_id": item.get("vod_id"),
            "vod_name": item.get("vod_name"),
            "vod_pic": item.get("vod_pic", ""),
            "vod_remarks": item.get("vod_remarks", ""),
            "vod_year": item.get("vod_year", ""),
            "vod_content": item.get("vod_content", ""),
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }

# 全局聚合搜索单例
aggregator = Aggregator()
