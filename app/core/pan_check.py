import re
import asyncio
import httpx
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from app.core.cache import pan_check_cache
from app.config import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# 支持的网盘类型与链接正则
PAN_PATTERNS = [
    ("quark",  r'https?://pan\.quark\.cn/s/[a-zA-Z0-9]+'),
    ("ali",    r'https?://(?:www\.)?(?:alipan\.com|aliyundrive\.com)/s/[a-zA-Z0-9]+'),
    ("baidu",  r'https?://pan\.baidu\.com/s/[a-zA-Z0-9_\-]+'),
    ("uc",     r'https?://drive\.uc\.cn/s/[a-zA-Z0-9]+'),
    ("xunlei", r'https?://pan\.xunlei\.com/s/[a-zA-Z0-9_\-]+'),
    ("115",    r'https?://(?:115\.com|anxia\.com)/s/[a-zA-Z0-9]+'),
    ("123",    r'https?://www\.123pan\.com/s/[a-zA-Z0-9\-]+'),
    ("tianyi", r'https?://cloud\.189\.cn/t/[a-zA-Z0-9]+'),
    ("magnet", r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+'),
]

PAN_DISPLAY_NAME = {
    "quark": "夸克网盘", "ali": "阿里云盘", "baidu": "百度网盘",
    "uc": "UC网盘", "xunlei": "迅雷网盘", "115": "115网盘",
    "123": "123网盘", "tianyi": "天翼云盘", "magnet": "磁力链接",
}


class PanCheck:
    """
    网盘有效性检测服务，支持两种模式：

    1. remote 模式 —— 对接自建的 PanCheck 服务 (dszz453/PanCheck)
       通过 PANCHECK_URL 环境变量配置，例如 http://192.168.1.10:8774
       优点：检测准确率高，支持 9 种主流网盘平台

    2. local 模式 —— 内置轻量探活
       直接请求分享页并根据关键字判断有效性，零依赖、零部署成本
       优点：开箱即用，无需额外服务
    """

    # ------------------------------------------------------------------
    # 链接提取
    # ------------------------------------------------------------------
    @staticmethod
    def extract_share_info(text: str) -> List[Dict[str, str]]:
        """从任意文本中提取网盘类型、分享链接和提取码"""
        if not text:
            return []

        results: List[Dict[str, str]] = []
        seen = set()

        for ptype, pattern in PAN_PATTERNS:
            for m in re.finditer(pattern, text, re.I):
                url = m.group(0)
                if url in seen:
                    continue
                seen.add(url)

                # 在链接后 40 个字符内寻找提取码
                pwd = ""
                tail = text[m.end():m.end() + 40]
                pwd_match = re.search(
                    r'(?:pwd|password|提取码|访问码|密码)\s*[:：=]?\s*([a-zA-Z0-9]{4,8})',
                    tail, re.I
                )
                if pwd_match:
                    pwd = pwd_match.group(1)
                else:
                    # 形如 "?pwd=abcd"
                    q = re.search(r'[?&]pwd=([a-zA-Z0-9]{4,8})', url, re.I)
                    if q:
                        pwd = q.group(1)

                results.append({"type": ptype, "url": url, "pwd": pwd})

        return results

    # ------------------------------------------------------------------
    # 对外主入口
    # ------------------------------------------------------------------
    @classmethod
    async def filter_valid_links(cls, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并发过滤失效链接（自动选择 remote / local 模式）"""
        if not links or not config.pan_check_enabled:
            return links

        # 磁力链接不做探活（没有稳定的 HTTP 探活方式）
        checkable = [l for l in links if l.get("type") != "magnet"]
        skipped = [l for l in links if l.get("type") == "magnet"]

        if not checkable:
            return links

        if config.use_remote_pancheck:
            valid = await cls._check_remote_batch(checkable)
        else:
            valid = await cls._check_local_batch(checkable)

        return valid + skipped

    # ------------------------------------------------------------------
    # 模式一：远程 PanCheck 服务
    # ------------------------------------------------------------------
    @classmethod
    async def _check_remote_batch(cls, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """调用自建 PanCheck 服务批量检测"""
        urls = [l.get("url", "") for l in links]
        url_set = set(urls)

        # 先查缓存
        uncached = []
        result_map: Dict[str, bool] = {}
        for u in urls:
            c = pan_check_cache.get(u)
            if c is None:
                uncached.append(u)
            else:
                result_map[u] = c

        # 分批请求远程服务
        if uncached:
            batch_size = config.PANCHECK_BATCH_SIZE
            batches = [uncached[i:i + batch_size] for i in range(0, len(uncached), batch_size)]

            tasks = [cls._call_remote_pancheck(b) for b in batches]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for br in batch_results:
                if isinstance(br, dict):
                    for u, ok in br.items():
                        result_map[u] = ok
                        pan_check_cache.set(u, ok)

        # 远程服务未返回结果的链接，回退到本地探活
        missing = [u for u in url_set if u not in result_map]
        if missing:
            missing_links = [l for l in links if l.get("url") in set(missing)]
            local_valid = await cls._check_local_batch(missing_links)
            local_valid_urls = {l.get("url") for l in local_valid}
            for u in missing:
                result_map[u] = u in local_valid_urls

        return [l for l in links if result_map.get(l.get("url", ""), True)]

    @classmethod
    async def _call_remote_pancheck(cls, urls: List[str]) -> Dict[str, bool]:
        """
        调用远程 PanCheck，兼容多种常见 API 形态：
          POST {base}/api/check   {"links": [...]}
          POST {base}/api/validate {"urls": [...]}
          GET  {base}/api/check?url=...
        返回 {url: is_valid}
        """
        base = config.PANCHECK_URL
        if not base:
            return {}

        timeout = httpx.Timeout(max(config.PANCHECK_TIMEOUT, 3.0) * len(urls) ** 0.5,
                                connect=config.PANCHECK_TIMEOUT + 2)

        payloads = [
            ("POST", f"{base}/api/check",    {"links": urls}),
            ("POST", f"{base}/api/validate", {"urls": urls}),
            ("POST", f"{base}/check",        {"links": urls}),
            ("POST", f"{base}/api/links/check", {"links": urls}),
        ]

        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            for method, url, body in payloads:
                try:
                    resp = await client.post(url, json=body, headers={"Accept": "application/json"})
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    parsed = cls._parse_remote_response(data, urls)
                    if parsed:
                        return parsed
                except Exception:
                    continue

            # 退化为逐个 GET
            result: Dict[str, bool] = {}
            for u in urls:
                for ep in (f"{base}/api/check", f"{base}/check"):
                    try:
                        r = await client.get(ep, params={"url": u},
                                             headers={"Accept": "application/json"})
                        if r.status_code == 200:
                            parsed = cls._parse_remote_response(r.json(), [u])
                            if parsed:
                                result.update(parsed)
                                break
                    except Exception:
                        continue
            return result

    @staticmethod
    def _parse_remote_response(data: Any, urls: List[str]) -> Dict[str, bool]:
        """解析远程 PanCheck 的多种返回结构"""
        out: Dict[str, bool] = {}
        if data is None:
            return out

        # 形态 A: {"url": true/false, ...}
        if isinstance(data, dict) and all(isinstance(v, bool) for v in data.values()) and data:
            for k, v in data.items():
                if k in urls or k.startswith("http"):
                    out[k] = bool(v)
            if out:
                return out

        # 形态 B: {"data": [...]} / {"results": [...]} / 直接是 list
        items = None
        if isinstance(data, dict):
            for key in ("data", "results", "list", "items", "links"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            if items is None and "success" in data and isinstance(data.get("valid"), list):
                items = data["valid"]
        elif isinstance(data, list):
            items = data

        if not isinstance(items, list):
            return out

        for it in items:
            if isinstance(it, str):
                out[it] = True
                continue
            if not isinstance(it, dict):
                continue
            u = it.get("url") or it.get("link") or it.get("share_url") or ""
            if not u:
                continue
            # 尝试各种有效性字段
            for f in ("valid", "is_valid", "ok", "success", "alive", "status"):
                if f in it:
                    v = it[f]
                    if isinstance(v, bool):
                        out[u] = v
                    elif isinstance(v, str):
                        out[u] = v.lower() in ("ok", "valid", "true", "success", "alive", "1")
                    elif isinstance(v, int):
                        out[u] = v == 1
                    break
            else:
                # 没有明确字段时，看是否含错误信息
                err = str(it.get("error", "")) + str(it.get("message", ""))
                out[u] = not any(k in err for k in ("失效", "不存在", "已删除", "取消", "过期", "invalid", "not found"))

        return out

    # ------------------------------------------------------------------
    # 模式二：内置轻量探活
    # ------------------------------------------------------------------
    @classmethod
    async def _check_local_batch(cls, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """内置并发探活，超时或异常时默认放行（避免误杀）"""
        if not links:
            return []

        tasks = [cls.check_url(l.get("url", ""), l.get("type", "")) for l in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid = []
        for item, res in zip(links, results):
            if isinstance(res, Exception) or res is True:
                valid.append(item)
        return valid

    @classmethod
    async def check_url(cls, url: str, pan_type: str = "") -> bool:
        """检测单个网盘链接是否有效（带缓存）"""
        if not url:
            return False
        if not config.pan_check_enabled:
            return True

        cached = pan_check_cache.get(url)
        if cached is not None:
            return cached

        is_valid = True
        try:
            parsed = urlparse(url)
            domain = (parsed.netloc or "").lower()
            if not pan_type:
                pan_type = cls._guess_type(domain)

            timeout = httpx.Timeout(config.PANCHECK_TIMEOUT, connect=config.PANCHECK_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                         verify=False, headers=HEADERS) as client:
                resp = await client.get(url)
                text = resp.text or ""
                is_valid = cls._judge(pan_type, resp.status_code, text)
        except Exception:
            # 网络波动、超时一律放行，宁可多留也不误杀
            is_valid = True

        pan_check_cache.set(url, is_valid)
        return is_valid

    @staticmethod
    def _guess_type(domain: str) -> str:
        if "quark" in domain:
            return "quark"
        if "alipan" in domain or "aliyundrive" in domain:
            return "ali"
        if "baidu" in domain:
            return "baidu"
        if "uc.cn" in domain:
            return "uc"
        if "xunlei" in domain:
            return "xunlei"
        if "115" in domain or "anxia" in domain:
            return "115"
        if "123pan" in domain:
            return "123"
        if "189.cn" in domain:
            return "tianyi"
        return "unknown"

    @staticmethod
    def _judge(pan_type: str, status_code: int, text: str) -> bool:
        """根据各网盘失效关键字判定"""
        if status_code in (404, 410):
            return False

        invalid_keywords = {
            "quark":  ("该分享已失效", "分享已被删除", "文件不存在", "分享已过期", "page404"),
            "ali":    ("分享已失效", "文件不存在", "已被分享者取消", "分享不存在", "链接已失效"),
            "baidu":  ("给您分享的文件已经被取消", "页面不存在", "此链接分享内容可能",
                       "分享的文件已经被删除", "你访问的页面不存在"),
            "uc":     ("分享已失效", "文件不存在", "已被删除", "链接失效"),
            "xunlei": ("分享已失效", "文件不存在", "已被删除"),
            "115":    ("该分享已关闭", "资源不存在", "分享已失效"),
            "123":    ("分享已失效", "文件不存在", "已取消分享"),
            "tianyi": ("分享已失效", "文件不存在", "链接不存在"),
        }
        for kw in invalid_keywords.get(pan_type, ()):
            if kw in text:
                return False
        return True
