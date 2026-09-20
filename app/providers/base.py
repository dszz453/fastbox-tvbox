from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseProvider(ABC):
    """搜索源基类"""
    def __init__(self, name: str, enabled: bool = True, timeout: float = 3.0):
        self.name = name
        self.enabled = enabled
        self.timeout = timeout

    @abstractmethod
    async def search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        异步搜索实现
        :param keyword: 关键词
        :return: 资源列表
        """
        pass
