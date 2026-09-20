"""
阿里云盘扫码授权登录

流程：
  1. generate  → 生成二维码（返回二维码内容 URL + ck + t）
  2. query     → 轮询扫码状态 NEW / SCANED / CONFIRMED / EXPIRED
  3. CONFIRMED → 从 bizExt(base64) 解出 refreshToken
  4. exchange  → 调用 ALI_OPEN_API_URL 用 refreshToken 换取 open_token（TVBox 播放所需）

说明：云盘接口可能随官方调整而变化，本模块对异常做了完整兜底，
      若扫码流程失效，用户仍可通过「手动填写」方式配置密钥。
"""
import base64
import json
import time
from typing import Dict, Any, Optional

import httpx

PASSPORT_BASE = "https://passport.aliyundrive.com"
GEN_URL = f"{PASSPORT_BASE}/newlogin/qrcode/generate.do"
QRY_URL = f"{PASSPORT_BASE}/newlogin/qrcode/query.do"

COMMON_PARAMS = {
    "appName": "aliyun_drive",
    "fromSite": "52",
    "appEntrance": "web",
    "_bx-v": "2.5.31",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.aliyundrive.com/",
    "Origin": "https://www.aliyundrive.com",
    "Accept": "application/json, text/plain, */*",
}

# 扫码会话缓存: sid -> {ck, t, created_at}
_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TTL = 300  # 5 分钟


def _cleanup_sessions() -> None:
    now = time.time()
    for k in [k for k, v in _SESSIONS.items() if now - v.get("created_at", 0) > SESSION_TTL]:
        _SESSIONS.pop(k, None)


async def generate_qr(sid: str) -> Dict[str, Any]:
    """生成阿里云盘登录二维码"""
    _cleanup_sessions()

    async with httpx.AsyncClient(timeout=8.0, verify=False, headers=HEADERS,
                                 follow_redirects=True) as client:
        resp = await client.post(GEN_URL, params=COMMON_PARAMS, data={})
        resp.raise_for_status()
        data = resp.json()

    content = (data or {}).get("content") or {}
    inner = content.get("data") or {}

    qr_content = inner.get("codeContent") or inner.get("qrCodeUrl") or ""
    ck = inner.get("ck") or ""
    t = inner.get("t") or ""

    if not qr_content or not ck:
        raise RuntimeError(f"二维码生成失败: {json.dumps(data, ensure_ascii=False)[:300]}")

    _SESSIONS[sid] = {"ck": ck, "t": t, "created_at": time.time()}

    return {
        "qr_content": qr_content,   # 前端把它渲染成二维码图片
        "sid": sid,
        "expires_in": SESSION_TTL,
    }


async def poll_qr(sid: str) -> Dict[str, Any]:
    """轮询扫码状态"""
    _cleanup_sessions()

    sess = _SESSIONS.get(sid)
    if not sess:
        return {"status": "EXPIRED", "message": "二维码已过期，请刷新重试"}

    params = dict(COMMON_PARAMS)
    params.update({"ck": sess["ck"], "t": sess["t"]})

    async with httpx.AsyncClient(timeout=8.0, verify=False, headers=HEADERS,
                                 follow_redirects=True) as client:
        resp = await client.post(QRY_URL, params=params, data={})
        resp.raise_for_status()
        data = resp.json()

    content = (data or {}).get("content") or {}
    inner = content.get("data") or {}

    status = (inner.get("qrCodeStatus") or "").upper()

    if status == "NEW":
        return {"status": "WAITING", "message": "等待扫码…"}
    if status == "SCANED":
        return {"status": "SCANNED", "message": "已扫码，请在手机上确认登录"}
    if status == "EXPIRED":
        _SESSIONS.pop(sid, None)
        return {"status": "EXPIRED", "message": "二维码已过期，请刷新重试"}
    if status == "CONFIRMED":
        refresh_token, access_token = _extract_tokens(inner.get("bizExt"))
        _SESSIONS.pop(sid, None)
        if not refresh_token:
            return {"status": "ERROR", "message": "登录成功但未能解析到凭证，请改用手动填写"}
        return {
            "status": "CONFIRMED",
            "message": "登录成功",
            "refresh_token": refresh_token,
            "access_token": access_token or "",
        }

    return {"status": "UNKNOWN", "message": f"未知状态: {status or '空'}"}


def _extract_tokens(biz_ext: Optional[str]):
    """bizExt 是 base64 编码的 JSON，内含 refreshToken / accessToken"""
    if not biz_ext:
        return "", ""
    try:
        raw = base64.b64decode(biz_ext).decode("utf-8", errors="ignore")
        obj = json.loads(raw)
    except Exception:
        return "", ""

    result = obj.get("pds_login_result") or obj
    refresh_token = result.get("refreshToken") or result.get("refresh_token") or ""
    access_token = result.get("accessToken") or result.get("access_token") or ""
    return refresh_token, access_token


async def exchange_open_token(refresh_token: str, open_api_url: str) -> Dict[str, str]:
    """
    用 refresh_token 换取 open_token（TVBox / pg.jar 播放网盘原画所需）

    open_api_url 格式支持： "postparam|http://xxx" 或 "http://xxx"
    """
    if not refresh_token:
        return {"open_token": "", "access_token": "", "refresh_token": ""}

    url = open_api_url
    mode = "postjson"
    if "|" in open_api_url:
        mode, url = open_api_url.split("|", 1)
        mode = mode.strip().lower()

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False,
                                     follow_redirects=True, headers=HEADERS) as client:
            if mode == "postparam":
                resp = await client.post(url, data={"code": refresh_token})
            else:
                resp = await client.post(url, json={"code": refresh_token})

            if resp.status_code != 200:
                return {"open_token": "", "access_token": "", "refresh_token": refresh_token}

            data = resp.json()
            # 兼容多种返回结构
            d = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
            if not isinstance(d, dict):
                d = {}
            return {
                "open_token": d.get("open_token") or d.get("openToken") or "",
                "access_token": d.get("access_token") or d.get("accessToken") or "",
                "refresh_token": d.get("refresh_token") or d.get("refreshToken") or refresh_token,
            }
    except Exception:
        return {"open_token": "", "access_token": "", "refresh_token": refresh_token}
