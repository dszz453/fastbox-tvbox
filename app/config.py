import os

class Config:
    # 基础服务配置
    PORT = int(os.getenv("PORT", "8088"))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # 默认首页类型: douban(豆瓣热播首页), fastbox(极速聚合搜索首页), full(全能影视首页)
    DEFAULT_HOME = os.getenv("DEFAULT_HOME", "douban")
    
    # 全局搜索超时(秒)，多源并发请求时防止单源卡死，保障极速响应
    SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "3.0"))
    
    # 缓存有效期(秒)
    CACHE_TTL_SEARCH = int(os.getenv("CACHE_TTL_SEARCH", "1800"))   # 搜索缓存30分钟
    CACHE_TTL_DOUBAN = int(os.getenv("CACHE_TTL_DOUBAN", "7200"))   # 豆瓣首页缓存2小时
    CACHE_TTL_PAN_CHECK = int(os.getenv("CACHE_TTL_PAN_CHECK", "86400")) # 网盘探活缓存24小时
    
    # 是否启用 PanCheck 网盘死链过滤
    ENABLE_PAN_CHECK = os.getenv("ENABLE_PAN_CHECK", "true").lower() == "true"
    PAN_CHECK_TIMEOUT = float(os.getenv("PAN_CHECK_TIMEOUT", "1.5"))
    
    # 最大并发任务数
    MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "20"))
    
    # 豆瓣图片防盗链代理开关
    ENABLE_IMG_PROXY = True
    
    # 用户可自定义的网盘 Token 文件路径 (挂载配置)
    TOKEN_FILE = os.getenv("TOKEN_FILE", "static/pg/lib/tokenm.json")

config = Config()
