import uuid
import time
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import config
from app.core.runtime_config import runtime_store, MUTABLE_SCHEMA
from app.core import aliyun_qr

router = APIRouter(prefix="/api", tags=["系统配置与扫码授权"])


# ======================================================================
# 一、网页可视化配置
# ======================================================================

def _current_value(key: str) -> Any:
    """读取某项配置当前生效值（网页配置优先，否则 env 默认）"""
    prop_map = {
        "default_home": "DEFAULT_HOME",
        "search_timeout": "SEARCH_TIMEOUT",
        "max_concurrency": "MAX_CONCURRENCY",
        "enable_img_proxy": "ENABLE_IMG_PROXY",
        "enable_danmu": "ENABLE_DANMU",
        "enable_pansou_edge": "ENABLE_PANSOU_EDGE",
        "pansou_edge_url": "PANSOU_EDGE_URL",
        "pansou_edge_token": "PANSOU_EDGE_TOKEN",
        "pansou_edge_timeout": "PANSOU_EDGE_TIMEOUT",
        "pancheck_mode": "PANCHECK_MODE",
        "pancheck_url": "PANCHECK_URL",
        "pancheck_timeout": "PANCHECK_TIMEOUT",
        "pancheck_batch_size": "PANCHECK_BATCH_SIZE",
        "cache_ttl_search": "CACHE_TTL_SEARCH",
        "cache_ttl_douban": "CACHE_TTL_DOUBAN",
    }
    attr = prop_map.get(key)
    return getattr(config, attr) if attr else None


@router.get("/settings")
async def get_settings():
    """获取全部可网页配置项（含当前值、是否被网页覆盖）"""
    overrides = runtime_store.all()
    items = []
    for key, typ in MUTABLE_SCHEMA.items():
        items.append({
            "key": key,
            "value": _current_value(key),
            "type": typ.__name__,
            "overridden": key in overrides,
        })
    return {
        "code": 200,
        "data": items,
        "config_file": runtime_store.path,
        "note": "网页修改的配置优先级高于环境变量，重启容器后依然保留",
    }


class SettingsPayload(BaseModel):
    settings: Dict[str, Any]


@router.post("/settings")
async def update_settings(payload: SettingsPayload):
    """保存网页配置（仅接受白名单内的键）"""
    invalid = [k for k in payload.settings if k not in MUTABLE_SCHEMA]
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的配置项: {', '.join(invalid)}")
    try:
        runtime_store.update(payload.settings)
        if not runtime_store.save():
            raise HTTPException(status_code=500, detail="写入配置文件失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "code": 200,
        "msg": "配置已保存并立即生效",
        "data": {k: _current_value(k) for k in payload.settings},
    }


@router.post("/settings/reset")
async def reset_settings():
    """清空网页配置，回退到环境变量默认值"""
    runtime_store.reset()
    return {"code": 200, "msg": "已恢复为环境变量默认配置"}


# ======================================================================
# 二、连通性测试
# ======================================================================

@router.post("/settings/test/pansou")
async def test_pansou(url: Optional[str] = None, token: Optional[str] = None):
    """测试 pansou-edge 自建节点是否可用"""
    target = (url or config.PANSOU_EDGE_URL).rstrip("/")
    if not target:
        return {"code": 400, "ok": False, "msg": "尚未填写 pansou-edge 地址"}

    headers = {"Accept": "application/json", "User-Agent": "FastBox/1.0"}
    tk = token or config.PANSOU_EDGE_TOKEN
    if tk:
        headers["Authorization"] = f"Bearer {tk}"

    tried = []
    async with httpx.AsyncClient(timeout=8.0, verify=False,
                                 follow_redirects=True, headers=headers) as client:
        for path in ("/api/search", "/search", "/api/health", "/health", "/"):
            u = target + path
            try:
                params = {"kw": "测试", "q": "测试"} if "search" in path else {}
                r = await client.get(u, params=params)
                tried.append(f"{path} -> HTTP {r.status_code}")
                if r.status_code == 200:
                    body = r.text[:200]
                    is_json = body.strip().startswith("{") or body.strip().startswith("[")
                    return {
                        "code": 200, "ok": True,
                        "msg": f"连接成功（{path}）",
                        "detail": f"HTTP 200，返回{'JSON' if is_json else '非JSON'}数据",
                        "tried": tried,
                    }
            except Exception as e:
                tried.append(f"{path} -> {type(e).__name__}")

    return {"code": 200, "ok": False, "msg": "无法连接到该地址，请检查 URL / 网络 / 鉴权", "tried": tried}


@router.post("/settings/test/pancheck")
async def test_pancheck(url: Optional[str] = None):
    """测试自建 PanCheck 服务是否可用"""
    target = (url or config.PANCHECK_URL).rstrip("/")
    if not target:
        return {"code": 400, "ok": False, "msg": "尚未填写 PanCheck 地址"}

    tried = []
    async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
        for path in ("/api/health", "/health", "/api/check", "/"):
            u = target + path
            try:
                r = await client.get(u)
                tried.append(f"{path} -> HTTP {r.status_code}")
                if r.status_code < 500:
                    return {
                        "code": 200, "ok": True,
                        "msg": f"连接成功（{path}）",
                        "detail": f"HTTP {r.status_code}",
                        "tried": tried,
                    }
            except Exception as e:
                tried.append(f"{path} -> {type(e).__name__}")

    return {"code": 200, "ok": False, "msg": "无法连接到该地址，请检查 URL / 端口 / 网络", "tried": tried}


# ======================================================================
# 三、阿里云盘扫码授权登录
# ======================================================================

@router.post("/qr/aliyun/generate")
async def aliyun_qr_generate():
    """生成阿里云盘扫码登录二维码"""
    sid = uuid.uuid4().hex
    try:
        data = await aliyun_qr.generate_qr(sid)
        return {"code": 200, "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"二维码生成失败: {e}")


@router.get("/qr/aliyun/poll")
async def aliyun_qr_poll(sid: str = Query(...)):
    """轮询扫码状态"""
    try:
        data = await aliyun_qr.poll_qr(sid)
        return {"code": 200, "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"轮询失败: {e}")


class AliyunSavePayload(BaseModel):
    refresh_token: str = ""
    open_token: str = ""
    access_token: str = ""


@router.post("/qr/aliyun/save")
async def aliyun_qr_save(payload: AliyunSavePayload):
    """
    扫码确认后保存凭证：
      - refresh_token 写入 tokenm.json 的 token 字段
      - 若配置了 ALI_OPEN_API_URL，自动兑换 open_token 一并写入
    """
    from app.routers.token_api import _load_token_file, _save_token_file

    refresh_token = payload.refresh_token.strip()
    open_token = payload.open_token.strip()

    if not refresh_token and not open_token:
        raise HTTPException(status_code=400, detail="缺少凭证")

    # 自动兑换 open_token
    if not open_token and refresh_token:
        try:
            ex = await aliyun_qr.exchange_open_token(refresh_token, config.ALI_OPEN_API_URL)
            open_token = ex.get("open_token", "")
        except Exception:
            open_token = ""

    data = _load_token_file()
    if refresh_token:
        data["token"] = refresh_token
    if open_token:
        data["open_token"] = open_token
    _save_token_file(data)

    return {
        "code": 200,
        "msg": "阿里云盘登录成功，凭证已保存！",
        "data": {
            "has_refresh_token": bool(refresh_token),
            "has_open_token": bool(open_token),
            "hint": "已获取 open_token" if open_token else "未获取到 open_token，仅保存了 refresh_token",
        },
    }


# ======================================================================
# 四、其他网盘「扫码填写」移动端页面
# ======================================================================

MOBILE_FIELD_MAP = {
    "quark":   {"title": "夸克网盘 Cookie", "field": "quark_cookie",
                "placeholder": "_UP_A4A_HP=...; b-user-id=...",
                "tip": "手机浏览器登录 pan.quark.cn → 开发者工具 → 复制 Cookie"},
    "uc":      {"title": "UC 网盘 Cookie", "field": "uc_cookie",
                "placeholder": "复制 drive.uc.cn 的完整 Cookie",
                "tip": "手机浏览器登录 drive.uc.cn → 复制 Cookie"},
    "115":     {"title": "115 网盘 Cookie", "field": "yd_auth",
                "placeholder": "复制 115.com 的 Cookie",
                "tip": "手机浏览器登录 115.com → 复制 Cookie"},
    "thunder": {"title": "迅雷网盘账号", "field": "thunder_username",
                "placeholder": "迅雷账号（手机号/邮箱）",
                "tip": "输入迅雷账号，密码可在网页端补充"},
    "pikpak":  {"title": "PikPak 账号", "field": "pikpak_username",
                "placeholder": "PikPak 账号（手机号/邮箱）",
                "tip": "输入 PikPak 账号，密码可在网页端补充"},
}


@router.get("/qr/mobile/{kind}", response_class=HTMLResponse)
async def mobile_fill_page(kind: str):
    """手机扫码后打开的填写页（让用户在手机上粘贴 Cookie，免去在电视上打字）"""
    meta = MOBILE_FIELD_MAP.get(kind)
    if not meta:
        return HTMLResponse("<h3>不支持的网盘类型</h3>", status_code=404)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{meta['title']}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       background:#0d1117;color:#f0f6fc;padding:24px 18px;line-height:1.6}}
  h1{{font-size:19px;margin-bottom:6px}}
  .tip{{font-size:13px;color:#8b949e;margin-bottom:18px}}
  textarea{{width:100%;min-height:140px;background:#161b22;border:1px solid #30363d;
           border-radius:10px;padding:14px;color:#f0f6fc;font-size:14px;
           font-family:ui-monospace,Menlo,Consolas,monospace;outline:none;resize:vertical}}
  textarea:focus{{border-color:#58a6ff}}
  button{{width:100%;margin-top:16px;padding:14px;background:#238636;color:#fff;
         border:none;border-radius:10px;font-size:16px;font-weight:600}}
  button:active{{background:#2ea043}}
  .ok{{color:#3fb950;text-align:center;margin-top:14px;font-size:14px;min-height:20px}}
</style>
</head>
<body>
  <h1>{meta['title']}</h1>
  <div class="tip">{meta['tip']}</div>
  <textarea id="val" placeholder="{meta['placeholder']}"></textarea>
  <button onclick="save()">保存到服务器</button>
  <div class="ok" id="msg"></div>
<script>
async function save() {{
  const v = document.getElementById('val').value.trim();
  if (!v) {{ document.getElementById('msg').textContent = '内容不能为空'; return; }}
  document.getElementById('msg').textContent = '保存中…';
  try {{
    const body = {{}}; body['{meta['field']}'] = v;
    const r = await fetch('/api/token', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify(body)
    }});
    const j = await r.json();
    document.getElementById('msg').textContent = j.msg || '保存成功！可以关闭本页了';
  }} catch(e) {{
    document.getElementById('msg').textContent = '保存失败: ' + e.message;
  }}
}}
</script>
</body>
</html>"""
    return HTMLResponse(html)
