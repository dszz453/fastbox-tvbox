import httpx
from typing import List, Dict, Any
from app.providers.base import BaseProvider

COLLECTOR_STATIONS = [
    {"name": "暴风秒播", "api": "https://bfzyapi.com/api.php/provide/vod"},
    {"name": "量子秒播", "api": "https://cj.lziapi.com/api.php/provide/vod"},
    {"name": "红牛高速", "api": "https://www.hongniuzy2.com/api.php/provide/vod"},
    {"name": "光速秒播", "api": "https://api.guangsuapi.com/api.php/provide/vod"},
    {"name": "非凡高清", "api": "http://cj.ffzyapi.com/api.php/provide/vod"},
    {"name": "卧龙秒播", "api": "https://collect.wolongzyw.com/api.php/provide/vod"},
    {"name": "极速专线", "api": "https://jszyapi.com/api.php/provide/vod"}
]

class CollectorProvider(BaseProvider):
    """
    基于 MacCMS V10 标准接口的影视切片采集站爬虫
    提供免网盘、直接播放的高清 m3u8 资源，秒开秒播
    """
    def __init__(self, name: str, api_url: str, timeout: float = 3.0):
        super().__init__(name=name, enabled=True, timeout=timeout)
        self.api_url = api_url

    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        results = []
        params = {
            "ac": "detail",
            "wd": keyword
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False, headers=headers) as client:
                resp = await client.get(self.api_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    vod_list = data.get("list", [])
                    for item in vod_list:
                        # 校验匹配度
                        title = item.get("vod_name", "").strip()
                        if not title:
                            continue
                        
                        play_from = item.get("vod_play_from", "")
                        play_url_raw = item.get("vod_play_url", "")
                        
                        episodes = self._parse_play_url(play_url_raw, play_from)
                        if not episodes:
                            continue

                        results.append({
                            "source": self.name,
                            "type": "collector",
                            "vod_id": f"col_{self.name}_{item.get('vod_id')}",
                            "title": title,
                            "category": item.get("type_name", "影视"),
                            "year": str(item.get("vod_year", "")),
                            "remarks": item.get("vod_remarks", "高清"),
                            "poster": item.get("vod_pic", ""),
                            "desc": item.get("vod_content", ""),
                            "episodes": episodes
                        })
        except Exception:
            # 某个采集站故障或超时，静默返回空，保障整体高速响应
            pass

        return results

    def _parse_play_url(self, play_url_raw: str, play_from: str) -> List[Dict[str, str]]:
        """
        解析 MacCMS 的 vod_play_url 格式：
        '第01集$https://...m3u8#第02集$https://...m3u8$$$线路2第01集$...'
        """
        episodes = []
        if not play_url_raw:
            return episodes

        # 分离不同播放来源
        sources = play_url_raw.split("$$$")
        # 优先选取包含 m3u8 的来源
        selected_source = sources[0]
        for src in sources:
            if "m3u8" in src:
                selected_source = src
                break

        # 分离剧集
        ep_list = selected_source.split("#")
        for ep in ep_list:
            if not ep.strip():
                continue
            parts = ep.split("$")
            if len(parts) >= 2:
                name = parts[0].strip()
                url = parts[1].strip()
            else:
                name = f"正片{len(episodes)+1}"
                url = parts[0].strip()

            if url.startswith("http"):
                episodes.append({
                    "name": name,
                    "url": url
                })
        return episodes
