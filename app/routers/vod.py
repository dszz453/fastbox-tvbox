from fastapi import APIRouter, Request, Query
from typing import Optional
from app.core.douban import DoubanService, DOUBAN_CATEGORIES
from app.core.aggregator import aggregator

router = APIRouter(prefix="/api", tags=["TVBox CMS/VOD 协议"])

@router.get("/vod")
async def vod_entry(
    request: Request,
    ac: Optional[str] = Query(None, description="操作指令: detail/videolist"),
    wd: Optional[str] = Query(None, description="搜索关键词"),
    ids: Optional[str] = Query(None, description="影视ID"),
    t: Optional[str] = Query(None, description="分类ID"),
    pg: int = Query(1, ge=1, description="页码")
):
    """
    兼容 MacCMS V10 标准的 VOD 影视接口
    无缝对接 TVBox、影视仓、猫影视、FongMi 等客户端
    """
    base_url = str(request.base_url).rstrip("/")

    # 1. 搜索模式 (ac=detail&wd=xxx 或直接传 wd)
    if wd:
        search_keyword = wd.strip()
        merged_items = await aggregator.search(search_keyword)
        vod_list = [aggregator.format_to_vod_item(item) for item in merged_items]
        return {
            "code": 1,
            "msg": "搜索结果",
            "page": 1,
            "pagecount": 1,
            "limit": len(vod_list),
            "total": len(vod_list),
            "list": vod_list
        }

    # 2. 详情模式 (ids=xxx)
    if ids:
        ids_str = ids.strip()
        # 如果是点击了豆瓣项目 (vod_id 形如 douban_12345_影片名)
        if ids_str.startswith("douban_"):
            parts = ids_str.split("_", 2)
            film_name = parts[2] if len(parts) >= 3 else ids_str
            # 用电影名去并发全网搜索全部播放线路
            merged_items = await aggregator.search(film_name)
            if merged_items:
                vod_list = [aggregator.format_to_vod_item(item) for item in merged_items]
                return {
                    "code": 1,
                    "msg": "详情与播放线路",
                    "page": 1,
                    "pagecount": 1,
                    "limit": len(vod_list),
                    "total": len(vod_list),
                    "list": vod_list
                }
            else:
                return {
                    "code": 1,
                    "msg": "暂无匹配线路",
                    "page": 1,
                    "pagecount": 1,
                    "limit": 0,
                    "total": 0,
                    "list": []
                }
        else:
            # 普通 ID 详情
            # 可以在搜索缓存或通过关键词尝试匹配
            merged_items = await aggregator.search(ids_str)
            vod_list = [aggregator.format_to_vod_item(item) for item in merged_items]
            return {
                "code": 1,
                "msg": "详情",
                "page": 1,
                "pagecount": 1,
                "limit": len(vod_list),
                "total": len(vod_list),
                "list": vod_list
            }

    # 3. 分类列表模式 (ac=detail&t=hot_movie&pg=1)
    if t:
        return await DoubanService.get_vod_list(type_id=t, page=pg, base_url=base_url)

    # 4. 默认返回首页数据与分类列表
    # 默认展示热门电影
    default_data = await DoubanService.get_vod_list(type_id="hot_movie", page=1, base_url=base_url)
    return default_data
