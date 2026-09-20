import json
import os
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from app.config import config

router = APIRouter(tags=["TVBox 订阅配置"])

JSM_FILE_PATH = "static/pg/jsm.json"

@router.get("/tvbox")
@router.get("/sub")
async def get_tvbox_config(
    request: Request,
    home: str = Query(None, description="首页类型: douban(默认豆瓣首页), lite(轻量极速), full(全量)")
):
    """
    生成 TVBox 标准订阅配置
    根据访问者的请求 Host 动态生成所有资源与 API 的绝对路径
    """
    base_url = str(request.base_url).rstrip("/")
    selected_home = home if home else config.DEFAULT_HOME

    # 1. 构建核心的极速聚合搜索 + 豆瓣首页站点
    douban_home_site = {
        "key": "fastbox_douban",
        "name": "🎬豆瓣热播·极速聚合",
        "type": 1,
        "api": f"{base_url}/api/vod",
        "searchable": 1,
        "quickSearch": 1,
        "filterable": 1
    }

    pure_search_site = {
        "key": "fastbox_search",
        "name": "🚀全网极速搜·秒播/网盘",
        "type": 1,
        "api": f"{base_url}/api/vod",
        "searchable": 1,
        "quickSearch": 1,
        "filterable": 0
    }

    # 2. 如果是轻量版
    if selected_home == "lite":
        cfg = {
            "spider": f"{base_url}/static/pg/pg.jar",
            "wallpaper": "https://bing.img.run/rand.php",
            "sites": [
                douban_home_site,
                pure_search_site
            ]
        }
        return JSONResponse(content=cfg)

    # 3. 如果存在本地 static/pg/jsm.json，则深度融合
    if os.path.exists(JSM_FILE_PATH):
        try:
            with open(JSM_FILE_PATH, "r", encoding="utf-8") as f:
                base_cfg = json.load(f)

            # 动态替换 spider 路径为本容器托管地址
            base_cfg["spider"] = f"{base_url}/static/pg/pg.jar"

            # 调整 sites 列表
            existing_sites = base_cfg.get("sites", [])

            # 替换其中的相对路径 ./lib/ 为绝对路径
            for s in existing_sites:
                ext = s.get("ext")
                if isinstance(ext, str) and "./" in ext:
                    s["ext"] = ext.replace("./", f"{base_url}/static/pg/")
                api = s.get("api")
                if isinstance(api, str) and "./" in api:
                    s["api"] = api.replace("./", f"{base_url}/static/pg/")

            # 根据用户选择的首页模式调整站点顺序
            if selected_home == "douban":
                # 将豆瓣首页放在第一位（TVBox 会默认打开第一个站点作为首页展示）
                # 并移除已有同名或冲突的默认站点，确保我们带高速防盗链反代和并发聚合搜索的豆瓣作为第 1 顺位！
                new_sites = [douban_home_site, pure_search_site]
                for s in existing_sites:
                    if s.get("key") not in ["豆瓣", "fastbox_douban", "fastbox_search"]:
                        new_sites.append(s)
                base_cfg["sites"] = new_sites
            else:
                # 聚合搜索放前面
                new_sites = [pure_search_site, douban_home_site]
                for s in existing_sites:
                    if s.get("key") not in ["fastbox_douban", "fastbox_search"]:
                        new_sites.append(s)
                base_cfg["sites"] = new_sites

            return JSONResponse(content=base_cfg)
        except Exception as e:
            print(f"[TVBox Router] merge jsm error: {e}")

    # 兜底配置
    fallback_cfg = {
        "spider": f"{base_url}/static/pg/pg.jar",
        "wallpaper": "https://bing.img.run/rand.php",
        "sites": [
            douban_home_site,
            pure_search_site
        ]
    }
    return JSONResponse(content=fallback_cfg)
