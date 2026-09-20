import httpx
from typing import List, Dict, Any
from urllib.parse import quote
from app.providers.base import BaseProvider
from app.core.pan_check import PanCheck

class PanSouEdgeProvider(BaseProvider):
    """
    网盘多源聚合搜索服务 (借鉴 dszz453/pansou-edge 与 OmniBox-Spider)
    汇聚 夸克、阿里、百度、迅雷、UC等云盘资源，并自动进行死链过滤
    """
    def __init__(self, timeout: float = 3.5):
        super().__init__(name="全网盘搜聚合", enabled=True, timeout=timeout)

    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        results = []
        # 并发请求多个公开可用的盘搜聚合节点
        sources = [
            self._search_node_yiso(keyword),
            self._search_node_quark_search(keyword),
            self._search_node_pan_hub(keyword)
        ]

        import asyncio
        node_results = await asyncio.gather(*sources, return_exceptions=True)
        all_links = []
        for r in node_results:
            if isinstance(r, list):
                all_links.extend(r)

        if not all_links:
            return results

        # 去重相同 URL
        seen_urls = set()
        unique_links = []
        for item in all_links:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_links.append(item)

        # 结合 PanCheck 探活过滤死链
        valid_links = await PanCheck.filter_valid_links(unique_links)
        if not valid_links:
            return results

        # 按照网盘类型分组合并
        quark_links = []
        ali_links = []
        baidu_links = []
        other_links = []

        for lk in valid_links:
            ptype = lk.get("type")
            title = lk.get("title", keyword)
            url = lk.get("url")
            pwd = lk.get("pwd", "")
            display_name = f"{title}" + (f" (提取码: {pwd})" if pwd else "")

            entry = {"name": display_name, "url": url}
            if ptype == "quark":
                quark_links.append(entry)
            elif ptype == "ali":
                ali_links.append(entry)
            elif ptype == "baidu":
                baidu_links.append(entry)
            else:
                other_links.append(entry)

        # 组装为 TVBox 线路
        grouped_results = []
        if quark_links:
            grouped_results.append({
                "source": "夸克4K原盘",
                "type": "pan",
                "vod_id": f"pan_quark_{quote(keyword)}",
                "title": f"【夸克专线】{keyword}",
                "category": "网盘4K",
                "remarks": f"共 {len(quark_links)} 个有效资源",
                "episodes": quark_links[:10]
            })
        if ali_links:
            grouped_results.append({
                "source": "阿里高清网盘",
                "type": "pan",
                "vod_id": f"pan_ali_{quote(keyword)}",
                "title": f"【阿里专线】{keyword}",
                "category": "网盘原画",
                "remarks": f"共 {len(ali_links)} 个有效资源",
                "episodes": ali_links[:10]
            })
        if baidu_links:
            grouped_results.append({
                "source": "百度网盘",
                "type": "pan",
                "vod_id": f"pan_baidu_{quote(keyword)}",
                "title": f"【百度专线】{keyword}",
                "category": "网盘资源",
                "remarks": f"共 {len(baidu_links)} 个有效资源",
                "episodes": baidu_links[:10]
            })
        if other_links:
            grouped_results.append({
                "source": "其他网盘资源",
                "type": "pan",
                "vod_id": f"pan_other_{quote(keyword)}",
                "title": f"【综合网盘】{keyword}",
                "category": "网盘资源",
                "remarks": f"共 {len(other_links)} 个有效资源",
                "episodes": other_links[:10]
            })

        return grouped_results

    async def _search_node_yiso(self, keyword: str):
        """易搜 / 阿里/夸克盘搜节点"""
        links = []
        url = f"https://api.yisou.fun/api/search?word={quote(keyword)}&page=1"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("list", [])
                    for it in items:
                        text = it.get("url", "") + " " + it.get("title", "")
                        extracted = PanCheck.extract_share_info(text)
                        for ex in extracted:
                            ex["title"] = it.get("title", keyword)
                            links.append(ex)
        except Exception:
            pass
        return links

    async def _search_node_quark_search(self, keyword: str):
        """夸克云搜 API 节点"""
        links = []
        url = f"https://pan.quark.cn/api/v1/search/public?kw={quote(keyword)}&page=1&size=10"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("list", [])
                    for it in items:
                        s_url = it.get("share_url") or it.get("url")
                        if s_url:
                            extracted = PanCheck.extract_share_info(s_url)
                            for ex in extracted:
                                ex["title"] = it.get("title", keyword)
                                links.append(ex)
        except Exception:
            pass
        return links

    async def _search_node_pan_hub(self, keyword: str):
        """综合网盘节点"""
        links = []
        # 通过公开聚合引擎抓取
        url = f"https://so.25pan.com/api/search?keyword={quote(keyword)}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    for it in items:
                        raw = str(it)
                        extracted = PanCheck.extract_share_info(raw)
                        for ex in extracted:
                            ex["title"] = it.get("name", keyword)
                            links.append(ex)
        except Exception:
            pass
        return links
