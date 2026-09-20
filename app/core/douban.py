import httpx
from urllib.parse import quote
from app.core.cache import douban_cache
from app.config import config

DOUBAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38",
    "Referer": "https://movie.douban.com/",
    "Accept": "application/json, text/plain, */*",
}

# 豆瓣分类定义
DOUBAN_CATEGORIES = [
    {"type_id": "hot_movie", "type_name": "🔥热门电影"},
    {"type_id": "new_movie", "type_name": "🆕最新电影"},
    {"type_id": "top_movie", "type_name": "🏆豆瓣Top250"},
    {"type_id": "hot_tv_cn", "type_name": "📺国产热播剧"},
    {"type_id": "hot_tv_us", "type_name": "🇺🇸欧美热播剧"},
    {"type_id": "hot_tv_kr", "type_name": "🇰🇷韩剧精选"},
    {"type_id": "hot_tv_jp", "type_name": "🇯🇵日剧精选"},
    {"type_id": "hot_anime", "type_name": "🌸热门动漫"},
    {"type_id": "hot_show", "type_name": "🎤热门综艺"}
]

class DoubanService:
    """
    豆瓣影视数据服务，提供热播、分类榜单以及格式转换
    """

    @classmethod
    def get_categories(cls):
        return DOUBAN_CATEGORIES

    @classmethod
    async def get_list_by_category(cls, type_id: str, page: int = 1, page_limit: int = 20, base_url: str = ""):
        """根据分类获取豆瓣影视列表，带内存高速缓存"""
        cache_key = f"douban:{type_id}:{page}:{page_limit}"
        cached = douban_cache.get(cache_key)
        if cached:
            return cached

        page_start = (page - 1) * page_limit
        url = ""
        
        if type_id == "hot_movie":
            url = f"https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "new_movie":
            url = f"https://movie.douban.com/j/search_subjects?type=movie&tag=%E6%9C%80%E6%96%B0&sort=time&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "top_movie":
            url = f"https://movie.douban.com/j/search_subjects?type=movie&tag=%E8%B1%86%E7%93%A3%E9%AB%98%E5%88%86&sort=rank&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_tv_cn":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E5%9B%BD%E4%BA%A7%E5%89%A7&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_tv_us":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E7%BE%8E%E5%89%A7&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_tv_kr":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E9%9F%A9%E5%89%A7&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_tv_jp":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E6%97%A5%E5%89%A7&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_anime":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E6%97%A5%E6%9C%AC%E5%8A%A8%E7%94%BB&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        elif type_id == "hot_show":
            url = f"https://movie.douban.com/j/search_subjects?type=tv&tag=%E7%BB%BC%E8%89%BA&sort=recommend&page_limit={page_limit}&page_start={page_start}"
        else:
            url = f"https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit={page_limit}&page_start={page_start}"

        items = []
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=DOUBAN_HEADERS, verify=False) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    subjects = data.get("subjects", [])
                    for s in subjects:
                        raw_pic = s.get("cover", "")
                        # 通过内置的图片代理加速并防盗链
                        pic_url = f"{base_url}/api/img?url={quote(raw_pic)}" if (base_url and config.ENABLE_IMG_PROXY) else raw_pic
                        rate = s.get("rate", "")
                        remarks = f"豆瓣 {rate}分" if rate else "热门推荐"
                        title = s.get("title", "")
                        sid = s.get("id", "")
                        
                        items.append({
                            "vod_id": f"douban_{sid}_{title}",
                            "vod_name": title,
                            "vod_pic": pic_url,
                            "vod_remarks": remarks,
                            "vod_year": s.get("year", ""),
                            "rate": rate,
                            "raw_pic": raw_pic
                        })
        except Exception as e:
            print(f"[DoubanService] fetch error: {e}")

        douban_cache.set(cache_key, items, ttl=config.CACHE_TTL_DOUBAN)
        return items

    @classmethod
    async def get_vod_list(cls, type_id: str, page: int = 1, base_url: str = ""):
        """封装为 TVBox/苹果CMS VOD 标准格式"""
        items = await cls.get_list_by_category(type_id, page=page, base_url=base_url)
        return {
            "code": 1,
            "msg": "数据列表",
            "page": page,
            "pagecount": 20,
            "limit": 20,
            "total": 400,
            "class": cls.get_categories(),
            "list": items
        }
