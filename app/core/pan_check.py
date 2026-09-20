import re
import httpx
import asyncio
from urllib.parse import urlparse
from app.core.cache import pan_check_cache
from app.config import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

class PanCheck:
    """
    网盘有效性快速检测服务 (借鉴 dszz453/PanCheck 设计理念)
    支持夸克网盘、阿里云盘、百度网盘、UC网盘等链接的秒级探活
    """

    @staticmethod
    def extract_share_info(text: str):
        """从字符串中提取网盘类型、链接和密码"""
        pan_patterns = [
            ("quark", r'https?://pan\.quark\.cn/s/[a-zA-Z0-9]+'),
            ("ali", r'https?://(?:www\.)?(?:alipan\.com|aliyundrive\.com)/s/[a-zA-Z0-9]+'),
            ("baidu", r'https?://pan\.baidu\.com/s/[a-zA-Z0-9_\-]+'),
            ("uc", r'https?://drive\.uc\.cn/s/[a-zA-Z0-9]+'),
            ("xunlei", r'https?://pan\.xunlei\.com/s/[a-zA-Z0-9_\-]+'),
            ("115", r'https?://115\.com/s/[a-zA-Z0-9]+'),
            ("123", r'https?://www.123pan\.com/s/[a-zA-Z0-9\-]+')
        ]
        
        results = []
        for ptype, pattern in pan_patterns:
            matches = re.finditer(pattern, text)
            for m in matches:
                url = m.group(0)
                # 尝试提取密码 (pwd / 提取码 / 密码)
                pwd = ""
                pwd_match = re.search(r'(?:pwd|提取码|密码)[：:\s]*([a-zA-Z0-9]{4})', text[m.end():m.end()+30], re.I)
                if pwd_match:
                    pwd = pwd_match.group(1)
                results.append({"type": ptype, "url": url, "pwd": pwd})
        return results

    @classmethod
    async def check_url(cls, url: str) -> bool:
        """
        异步检测单一网盘链接是否有效
        使用带 TTL 的缓存，避免对同一个链接反复网络请求
        """
        if not config.ENABLE_PAN_CHECK:
            return True

        cached = pan_check_cache.get(url)
        if cached is not None:
            return cached

        is_valid = True
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            timeout = httpx.Timeout(config.PAN_CHECK_TIMEOUT, connect=config.PAN_CHECK_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False, headers=HEADERS) as client:
                if "quark.cn" in domain:
                    # 夸克网盘检测
                    resp = await client.get(url)
                    text = resp.text
                    if "该分享已失效" in text or "分享已被删除" in text or "文件不存在" in text:
                        is_valid = False
                    elif "page404" in text or resp.status_code == 404:
                        is_valid = False
                elif "alipan.com" in domain or "aliyundrive.com" in domain:
                    # 阿里云盘检测
                    resp = await client.get(url)
                    text = resp.text
                    if "分享已失效" in text or "文件不存在" in text or "已被分享者取消" in text:
                        is_valid = False
                    elif resp.status_code in [404, 410]:
                        is_valid = False
                elif "baidu.com" in domain:
                    # 百度网盘检测
                    resp = await client.get(url)
                    text = resp.text
                    if "给您分享的文件已经被取消" in text or "页面不存在" in text or "此链接分享内容可能" in text:
                        is_valid = False
                    elif resp.status_code == 404:
                        is_valid = False
                elif "115.com" in domain:
                    # 115网盘检测
                    resp = await client.get(url)
                    text = resp.text
                    if "该分享已关闭" in text or "资源不存在" in text:
                        is_valid = False
                else:
                    # 其他网盘做简单状态码检测
                    resp = await client.head(url)
                    if resp.status_code in [404, 410]:
                        is_valid = False
        except Exception:
            # 网络超时或异常时默认放行，避免误杀正常资源
            is_valid = True

        pan_check_cache.set(url, is_valid)
        return is_valid

    @classmethod
    async def filter_valid_links(cls, links_list):
        """并发批量过滤失效链接"""
        if not links_list or not config.ENABLE_PAN_CHECK:
            return links_list

        tasks = [cls.check_url(item.get("url", "")) for item in links_list]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_items = []
        for item, res in zip(links_list, check_results):
            if res is True or isinstance(res, Exception):
                valid_items.append(item)
            # res is False 表示明确失效，过滤掉
        return valid_items
