import os
from app.core.runtime_config import runtime_store


def _env_bool(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes", "on")


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


class Config:
    """
    配置优先级：网页配置(data/runtime_config.json) > 环境变量 > 代码默认值

    - 标为 @property 的项，可在网页「系统设置」中实时修改并持久化
    - 其余项只能通过环境变量配置（属于启动期参数）
    """

    # ==================== 基础服务（env only） ====================
    APP_NAME = os.getenv("APP_NAME", "FastBox - TVBox 极速聚合搜索服务")
    PORT = int(os.getenv("PORT", "8088"))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = _env_bool("DEBUG", "false")

    # ==================== ① 可网页配置项（含 env 默认值） ====================
    _ENV_DEFAULT_HOME = _env_str("DEFAULT_HOME", "douban")
    _ENV_SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "3.0"))
    _ENV_MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "20"))
    _ENV_ENABLE_IMG_PROXY = _env_bool("ENABLE_IMG_PROXY", "true")
    _ENV_ENABLE_DANMU = _env_bool("ENABLE_DANMU", "true")

    _ENV_ENABLE_PANSOU_EDGE = _env_bool("ENABLE_PANSOU_EDGE", "true")
    _ENV_PANSOU_EDGE_URL = _env_str("PANSOU_EDGE_URL").rstrip("/")
    _ENV_PANSOU_EDGE_TOKEN = _env_str("PANSOU_EDGE_TOKEN")
    _ENV_PANSOU_EDGE_TIMEOUT = float(os.getenv("PANSOU_EDGE_TIMEOUT", "4.0"))

    _ENV_PANCHECK_MODE = _env_str("PANCHECK_MODE", "auto").lower()
    _ENV_PANCHECK_URL = _env_str("PANCHECK_URL").rstrip("/")
    _ENV_PANCHECK_TIMEOUT = float(os.getenv("PANCHECK_TIMEOUT", "1.5"))
    _ENV_PANCHECK_BATCH_SIZE = int(os.getenv("PANCHECK_BATCH_SIZE", "30"))

    _ENV_CACHE_TTL_SEARCH = int(os.getenv("CACHE_TTL_SEARCH", "1800"))
    _ENV_CACHE_TTL_DOUBAN = int(os.getenv("CACHE_TTL_DOUBAN", "7200"))

    # ---- 首页模式 ----
    @property
    def DEFAULT_HOME(self) -> str:
        return runtime_store.get("default_home", self._ENV_DEFAULT_HOME)

    # ---- 搜索性能 ----
    @property
    def SEARCH_TIMEOUT(self) -> float:
        return float(runtime_store.get("search_timeout", self._ENV_SEARCH_TIMEOUT))

    @property
    def MAX_CONCURRENCY(self) -> int:
        return int(runtime_store.get("max_concurrency", self._ENV_MAX_CONCURRENCY))

    @property
    def ENABLE_IMG_PROXY(self) -> bool:
        return bool(runtime_store.get("enable_img_proxy", self._ENV_ENABLE_IMG_PROXY))

    @property
    def ENABLE_DANMU(self) -> bool:
        return bool(runtime_store.get("enable_danmu", self._ENV_ENABLE_DANMU))

    # ---- pansou-edge 网盘聚合搜索 ----
    @property
    def ENABLE_PANSOU_EDGE(self) -> bool:
        return bool(runtime_store.get("enable_pansou_edge", self._ENV_ENABLE_PANSOU_EDGE))

    @property
    def PANSOU_EDGE_URL(self) -> str:
        return str(runtime_store.get("pansou_edge_url", self._ENV_PANSOU_EDGE_URL)).rstrip("/")

    @property
    def PANSOU_EDGE_TOKEN(self) -> str:
        return str(runtime_store.get("pansou_edge_token", self._ENV_PANSOU_EDGE_TOKEN))

    @property
    def PANSOU_EDGE_TIMEOUT(self) -> float:
        return float(runtime_store.get("pansou_edge_timeout", self._ENV_PANSOU_EDGE_TIMEOUT))

    # ---- PanCheck 网盘死链检测 ----
    @property
    def PANCHECK_MODE(self) -> str:
        return str(runtime_store.get("pancheck_mode", self._ENV_PANCHECK_MODE)).lower()

    @property
    def PANCHECK_URL(self) -> str:
        return str(runtime_store.get("pancheck_url", self._ENV_PANCHECK_URL)).rstrip("/")

    @property
    def PANCHECK_TIMEOUT(self) -> float:
        return float(runtime_store.get("pancheck_timeout", self._ENV_PANCHECK_TIMEOUT))

    @property
    def PANCHECK_BATCH_SIZE(self) -> int:
        return int(runtime_store.get("pancheck_batch_size", self._ENV_PANCHECK_BATCH_SIZE))

    # ---- 缓存 ----
    @property
    def CACHE_TTL_SEARCH(self) -> int:
        return int(runtime_store.get("cache_ttl_search", self._ENV_CACHE_TTL_SEARCH))

    @property
    def CACHE_TTL_DOUBAN(self) -> int:
        return int(runtime_store.get("cache_ttl_douban", self._ENV_CACHE_TTL_DOUBAN))

    CACHE_TTL_PAN_CHECK = int(os.getenv("CACHE_TTL_PAN_CHECK", "86400"))

    # ==================== ② 网盘播放密钥（扫码/网页配置） ====================
    # 密钥实际存储在 tokenm.json 中，这里仅保留文件路径等启动期参数
    TOKEN_FILE = _env_str("TOKEN_FILE", "static/pg/lib/tokenm.json")

    # 以下为环境变量兜底（容器启动时若检测到则写入 tokenm.json）
    ALI_TOKEN = _env_str("ALI_TOKEN")
    ALI_OPEN_TOKEN = _env_str("ALI_OPEN_TOKEN")
    QUARK_COOKIE = _env_str("QUARK_COOKIE")
    QUARK_IS_GUEST = _env_bool("QUARK_IS_GUEST", "false")
    UC_COOKIE = _env_str("UC_COOKIE")
    THUNDER_USERNAME = _env_str("THUNDER_USERNAME")
    THUNDER_PASSWORD = _env_str("THUNDER_PASSWORD")
    THUNDER_CAPTCHA_TOKEN = _env_str("THUNDER_CAPTCHA_TOKEN")
    PIKPAK_USERNAME = _env_str("PIKPAK_USERNAME")
    PIKPAK_PASSWORD = _env_str("PIKPAK_PASSWORD")
    YD_AUTH = _env_str("YD_AUTH")

    VOD_FLAGS = _env_str("VOD_FLAGS", "4kz|auto")
    VIP_THREAD_LIMIT = int(os.getenv("VIP_THREAD_LIMIT", "32"))
    QUARK_THREAD_LIMIT = int(os.getenv("QUARK_THREAD_LIMIT", "32"))
    UC_THREAD_LIMIT = int(os.getenv("UC_THREAD_LIMIT", "10"))
    THUNDER_THREAD_LIMIT = int(os.getenv("THUNDER_THREAD_LIMIT", "2"))

    # 阿里云盘 open_token 兑换接口（扫码登录后自动调用）
    ALI_OPEN_API_URL = _env_str(
        "ALI_OPEN_API_URL", "http://api.extscreen.com/aliyundrive/token"
    )

    # ==================== 派生属性 ====================
    @property
    def pan_check_enabled(self) -> bool:
        return self.PANCHECK_MODE != "off"

    @property
    def use_remote_pancheck(self) -> bool:
        mode = self.PANCHECK_MODE
        if mode == "off":
            return False
        if mode == "local":
            return False
        if mode == "remote":
            return bool(self.PANCHECK_URL)
        # auto
        return bool(self.PANCHECK_URL)

    @property
    def use_local_pancheck(self) -> bool:
        if self.PANCHECK_MODE == "off":
            return False
        return not self.use_remote_pancheck


config = Config()
