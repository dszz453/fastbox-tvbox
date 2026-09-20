import os
import json
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

router = APIRouter(prefix="/api/token", tags=["网盘 Token 配置"])

TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "pg", "lib", "tokentemplate.json")

class TokenConfig(BaseModel):
    ali_token: str = ""
    ali_open_token: str = ""
    quark_cookie: str = ""
    uc_cookie: str = ""
    thunder_username: str = ""
    thunder_password: str = ""

@router.get("")
async def get_token_config():
    """获取当前网盘 Token 配置"""
    if not os.path.exists(TOKEN_PATH):
        return {"code": 200, "data": {}}
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "code": 200,
                "data": {
                    "ali_token": data.get("token", ""),
                    "ali_open_token": data.get("open_token", ""),
                    "quark_cookie": data.get("quark_cookie", ""),
                    "uc_cookie": data.get("uc_cookie", ""),
                    "thunder_username": data.get("thunder_username", ""),
                    "thunder_password": data.get("thunder_password", "")
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def update_token_config(cfg: TokenConfig):
    """更新网盘 Token 配置"""
    try:
        data = {}
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        data["token"] = cfg.ali_token.strip()
        data["open_token"] = cfg.ali_open_token.strip()
        data["quark_cookie"] = cfg.quark_cookie.strip()
        data["uc_cookie"] = cfg.uc_cookie.strip()
        data["thunder_username"] = cfg.thunder_username.strip()
        data["thunder_password"] = cfg.thunder_password.strip()

        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {"code": 200, "msg": "网盘配置保存成功！TVBox 重新打开即可生效"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
