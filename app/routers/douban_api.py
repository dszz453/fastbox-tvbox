import httpx
from fastapi import APIRouter, Request, Response, Query
from app.core.douban import DoubanService
from app.core.cache import img_cache

router = APIRouter(prefix="/api", tags=["豆瓣与辅助服务"])

@router.get("/douban/categories")
async def get_douban_categories():
    """获取豆瓣支持的分类"""
    return {"code": 200, "data": DoubanService.get_categories()}

@router.get("/douban/list")
async def get_douban_list(
    request: Request,
    type_id: str = Query("hot_movie", description="分类ID"),
    page: int = Query(1, ge=1, description="页码")
):
    """获取豆瓣影视分类数据"""
    base_url = str(request.base_url).rstrip("/")
    items = await DoubanService.get_list_by_category(type_id=type_id, page=page, base_url=base_url)
    return {"code": 200, "page": page, "data": items}

@router.get("/img")
async def proxy_image(url: str = Query(..., description="原始图片链接")):
    """
    极速图片防盗链代理，突破豆瓣、微博等防盗链 403 限制
    并带有本地内存缓存，大幅提高 TVBox 海报加载速度
    """
    if not url.startswith("http"):
        return Response(status_code=400, content="Invalid url")

    # 优先读缓存
    cached = img_cache.get(url)
    if cached:
        return Response(content=cached["content"], media_type=cached["media_type"])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://movie.douban.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                media_type = resp.headers.get("content-type", "image/jpeg")
                content = resp.content
                # 缓存图片（最大 2MB）
                if len(content) <= 2 * 1024 * 1024:
                    img_cache.set(url, {"content": content, "media_type": media_type}, ttl=86400)
                return Response(content=content, media_type=media_type)
            else:
                return Response(status_code=resp.status_code, content="Image fetch failed")
    except Exception as e:
        return Response(status_code=502, content=f"Proxy error: {str(e)}")
