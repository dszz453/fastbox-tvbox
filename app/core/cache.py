import time
import asyncio
from typing import Any, Optional, Dict

class TTLCache:
    """
    轻量级高效内存 TTL 缓存器，支持异步与同步使用
    自动淘汰过期项，避免内存膨胀
    """
    def __init__(self, default_ttl: int = 1800, max_size: int = 2000):
        self._data: Dict[str, Any] = {}
        self._expire_times: Dict[str, float] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._lock = asyncio.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        exp = self._expire_times.get(key)
        if exp is None:
            return None
        if now > exp:
            self._remove(key)
            return None
        return self._data.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        now = time.time()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        
        # 简单容量控制
        if len(self._data) >= self.max_size:
            self._cleanup_expired()
            if len(self._data) >= self.max_size:
                # 丢弃最老的一批
                oldest_keys = sorted(self._expire_times.keys(), key=lambda k: self._expire_times[k])[:100]
                for k in oldest_keys:
                    self._remove(k)

        self._data[key] = value
        self._expire_times[key] = now + effective_ttl

    def delete(self, key: str) -> None:
        self._remove(key)

    def clear(self) -> None:
        self._data.clear()
        self._expire_times.clear()

    def _remove(self, key: str) -> None:
        self._data.pop(key, None)
        self._expire_times.pop(key, None)

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._expire_times.items() if now > exp]
        for k in expired:
            self._remove(k)

# 全局缓存单例
search_cache = TTLCache(default_ttl=1800, max_size=3000)
douban_cache = TTLCache(default_ttl=7200, max_size=500)
pan_check_cache = TTLCache(default_ttl=86400, max_size=10000)
img_cache = TTLCache(default_ttl=86400, max_size=1000)
