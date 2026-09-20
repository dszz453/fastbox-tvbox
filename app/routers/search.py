import time
from fastapi import APIRouter, Query
from app.core.aggregator import aggregator

router = APIRouter(prefix="/api", tags=["Web 搜索服务"])

@router.get("/search")
async def web_search(q: str = Query(..., description="搜索关键词")):
    """提供给 Web 控制台的极速多源搜索 API"""
    start = time.time()
    results = await aggregator.search(q.strip())
    elapsed = round((time.time() - start) * 1000, 2)
    return {
        "code": 200,
        "msg": "success",
        "query": q,
        "elapsed_ms": elapsed,
        "total": len(results),
        "data": results
    }
