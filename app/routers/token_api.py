import os
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import config

router = APIRouter(prefix="/api", tags=["网盘密钥与配置状态"])

# tokenm.json 的绝对路径（pg.jar 实际读取的位置）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(BASE_DIR, config.TOKEN_FILE.replace("/", os.sep))
# 镜像路径：位于数据卷内（docker-compose 挂载 ./data:/app/data），
# 容器重建后据此还原，解决「扫码保存成功、重建后又没了」的问题
PERSIST_PATH = os.path.join(BASE_DIR, config.DATA_DIR.replace("/", os.sep), "tokenm.json")


class TokenConfig(BaseModel):
    """网盘播放凭据"""
    ali_token: Optional[str] = ""
    ali_open_token: Optional[str] = ""
    quark_cookie: Optional[str] = ""
    uc_cookie: Optional[str] = ""
    thunder_username: Optional[str] = ""
    thunder_password: Optional[str] = ""
    pikpak_username: Optional[str] = ""
    pikpak_password: Optional[str] = ""
    yd_auth: Optional[str] = ""


def _read_json(path: str) -> Optional[dict]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return None


def _load_token_file() -> dict:
    """读取顺序：主路径 → 数据卷镜像 → 模板"""
    for p in (TOKEN_PATH, PERSIST_PATH):
        obj = _read_json(p)
        if obj:
            return obj
    tpl = os.path.join(BASE_DIR, "static", "pg", "lib", "tokentemplate.json")
    return _read_json(tpl) or {}


def _save_token_file(data: dict) -> None:
    """写入主路径，并镜像到数据卷，保证容器重建后凭证不丢。"""
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(payload)

    # 镜像失败不影响主流程（例如未挂载数据卷时）
    try:
        os.makedirs(os.path.dirname(PERSIST_PATH), exist_ok=True)
        with open(PERSIST_PATH, "w", encoding="utf-8") as f:
            f.write(payload)
    except Exception as e:
        print(f"[Token] 镜像写入失败（不影响本次保存）: {e}")


def ensure_token_file() -> None:
    """启动时调用：若主路径缺失但数据卷里有备份，则还原回主路径。"""
    if os.path.exists(TOKEN_PATH):
        return
    obj = _read_json(PERSIST_PATH)
    if not obj:
        return
    try:
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"[Token] 已从数据卷还原凭证 -> {TOKEN_PATH}")
    except Exception as e:
        print(f"[Token] 还原失败: {e}")


def apply_env_tokens() -> None:
    """
    容器启动时调用：把环境变量里的网盘密钥写入 tokenm.json。
    这样用户可以直接在 docker-compose.yml 里配置密钥，无需手动改文件。
    """
    env_map = {
        "token": config.ALI_TOKEN,
        "open_token": config.ALI_OPEN_TOKEN,
        "quark_cookie": config.QUARK_COOKIE,
        "uc_cookie": config.UC_COOKIE,
        "thunder_username": config.THUNDER_USERNAME,
        "thunder_password": config.THUNDER_PASSWORD,
        "thunder_captchatoken": config.THUNDER_CAPTCHA_TOKEN,
        "pikpak_username": config.PIKPAK_USERNAME,
        "pikpak_password": config.PIKPAK_PASSWORD,
        "yd_auth": config.YD_AUTH,
    }
    provided = {k: v for k, v in env_map.items() if v}

    data = _load_token_file()
    changed = False
    for k, v in provided.items():
        if data.get(k) != v:
            data[k] = v
            changed = True

    # 补齐画质与线程偏好
    if config.VOD_FLAGS and data.get("vod_flags") != config.VOD_FLAGS:
        data["vod_flags"] = config.VOD_FLAGS
        changed = True
    if data.get("danmu") != config.ENABLE_DANMU:
        data["danmu"] = config.ENABLE_DANMU
        changed = True

    if changed and data:
        try:
            _save_token_file(data)
            print(f"[Token] 已从环境变量写入 {len(provided)} 项网盘密钥 -> {TOKEN_PATH}")
        except Exception as e:
            print(f"[Token] 写入失败: {e}")


@router.get("/token")
async def get_token_config():
    """获取当前网盘密钥配置（脱敏展示）"""
    data = _load_token_file()

    def mask(v: str) -> str:
        if not v:
            return ""
        return v[:6] + "****" + v[-4:] if len(v) > 12 else "****"

    return {
        "code": 200,
        "data": {
            "ali_token": data.get("token", ""),
            "ali_open_token": data.get("open_token", ""),
            "quark_cookie": data.get("quark_cookie", ""),
            "uc_cookie": data.get("uc_cookie", ""),
            "thunder_username": data.get("thunder_username", ""),
            "thunder_password": data.get("thunder_password", ""),
            "pikpak_username": data.get("pikpak_username", ""),
            "pikpak_password": data.get("pikpak_password", ""),
            "yd_auth": data.get("yd_auth", ""),
        },
        "masked": {
            "ali_open_token": mask(data.get("open_token", "")),
            "quark_cookie": mask(data.get("quark_cookie", "")),
            "uc_cookie": mask(data.get("uc_cookie", "")),
        },
        "path": TOKEN_PATH,
        "persist_path": PERSIST_PATH,
    }


@router.post("/token")
async def update_token_config(cfg: TokenConfig):
    """更新网盘密钥并写入 tokenm.json"""
    try:
        data = _load_token_file()

        mapping = {
            "token": cfg.ali_token,
            "open_token": cfg.ali_open_token,
            "quark_cookie": cfg.quark_cookie,
            "uc_cookie": cfg.uc_cookie,
            "thunder_username": cfg.thunder_username,
            "thunder_password": cfg.thunder_password,
            "pikpak_username": cfg.pikpak_username,
            "pikpak_password": cfg.pikpak_password,
            "yd_auth": cfg.yd_auth,
        }
        for k, v in mapping.items():
            if v is not None and v != "":
                data[k] = v.strip()

        _save_token_file(data)
        return {
            "code": 200,
            "msg": "网盘密钥保存成功！TVBox 重新打开该影片即可生效",
            "path": TOKEN_PATH,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/config/status")
async def config_status():
    """
    配置自检面板：一眼看清哪些服务已配置、哪些还没配。
    不返回任何密钥明文，可安全暴露。
    """
    data = _load_token_file()

    def has(v) -> bool:
        return bool(str(v or "").strip())

    # 网盘密钥状态
    pan_keys = {
        "阿里云盘 (open_token)": has(data.get("open_token")),
        "阿里云盘 (refresh_token)": has(data.get("token")),
        "夸克网盘 (cookie)": has(data.get("quark_cookie")),
        "UC网盘 (cookie)": has(data.get("uc_cookie")),
        "迅雷网盘 (账号)": has(data.get("thunder_username")),
        "PikPak (账号)": has(data.get("pikpak_username")),
        "115网盘 (cookie)": has(data.get("yd_auth")),
    }

    return {
        "code": 200,
        "data": {
            "服务": {
                "默认首页": config.DEFAULT_HOME,
                "搜索超时(秒)": config.SEARCH_TIMEOUT,
                "并发上限": config.MAX_CONCURRENCY,
                "图片防盗链代理": config.ENABLE_IMG_PROXY,
                "弹幕": config.ENABLE_DANMU,
            },
            "pansou_edge": {
                "启用": config.ENABLE_PANSOU_EDGE,
                "自建地址": config.PANSOU_EDGE_URL or "（未配置，使用内置公开节点）",
                "候选地址数": len(config.PANSOU_EDGE_URLS),
                "候选地址列表": config.PANSOU_EDGE_URLS or [],
                "鉴权Token": "已配置" if config.PANSOU_EDGE_TOKEN else "未配置",
                "超时(秒)": config.PANSOU_EDGE_TIMEOUT,
            },
            "pancheck": {
                "启用": config.pan_check_enabled,
                "检测模式": config.PANCHECK_MODE,
                "实际生效": "远程 PanCheck 服务" if config.use_remote_pancheck
                            else ("内置轻量探活" if config.use_local_pancheck else "已关闭"),
                "自建地址": config.PANCHECK_URL or "（未配置）",
                "超时(秒)": config.PANCHECK_TIMEOUT,
                "批量大小": config.PANCHECK_BATCH_SIZE,
            },
            "网盘密钥": pan_keys,
            "密钥文件": TOKEN_PATH,
        },
    }
