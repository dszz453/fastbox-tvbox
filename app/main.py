import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader

from app.config import config
from app.routers.tvbox import router as tvbox_router
from app.routers.vod import router as vod_router
from app.routers.douban_api import router as douban_router
from app.routers.search import router as search_router
from app.routers.token_api import router as token_router

app = FastAPI(
    title=config.APP_NAME,
    description="支持 Docker 部署的 TVBox 极速多源聚合搜索服务与豆瓣热播首页订阅系统",
    version="1.0.0"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态资源
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板引擎
jinja_env = Environment(loader=FileSystemLoader("app/templates"))

# 注册路由
app.include_router(tvbox_router)
app.include_router(vod_router)
app.include_router(douban_router)
app.include_router(search_router)
app.include_router(token_router)

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Web 控制台主页"""
    template = jinja_env.get_template("index.html")
    return template.render()

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": config.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
