"""
运行时可变配置存储

设计目的：
  - 环境变量（docker-compose）提供「默认值」
  - 网页端修改的配置写入 data/runtime_config.json，并「覆盖」默认值
  - 重启容器后网页配置依然保留（data/ 目录挂载为卷）

优先级： 网页配置(runtime_config.json)  >  环境变量  >  代码内置默认值
"""
import os
import json
import threading
from typing import Any, Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "runtime_config.json")

# 允许网页端修改的配置项及其类型
MUTABLE_SCHEMA: Dict[str, type] = {
    # 首页与体验
    "default_home": str,          # douban | lite | full
    # 搜索性能
    "search_timeout": float,      # 单源熔断秒数
    "max_concurrency": int,
    "enable_img_proxy": bool,
    "enable_danmu": bool,
    # pansou-edge 网盘聚合搜索
    "enable_pansou_edge": bool,
    "pansou_edge_url": str,
    "pansou_edge_token": str,
    "pansou_edge_timeout": float,
    # PanCheck 网盘死链检测
    "pancheck_mode": str,         # auto | remote | local | off
    "pancheck_url": str,
    "pancheck_timeout": float,
    "pancheck_batch_size": int,
    # 缓存
    "cache_ttl_search": int,
    "cache_ttl_douban": int,
}


class RuntimeStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self.load()

    # ---------------- 持久化 ----------------
    def load(self) -> None:
        with self._lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict):
                        self._data = raw
                except Exception as e:
                    print(f"[RuntimeConfig] 读取失败，使用空配置: {e}")
                    self._data = {}

    def save(self) -> bool:
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
                return True
            except Exception as e:
                print(f"[RuntimeConfig] 保存失败: {e}")
                return False

    # ---------------- 读写 ----------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                v = self._data[key]
                # 类型归一化，容忍手工编辑造成的类型漂移
                t = MUTABLE_SCHEMA.get(key)
                try:
                    if t is bool:
                        if isinstance(v, str):
                            return v.strip().lower() in ("1", "true", "yes", "on")
                        return bool(v)
                    if t is int:
                        return int(v)
                    if t is float:
                        return float(v)
                    if t is str:
                        return str(v)
                except Exception:
                    return default
                return v
            return default

    def set(self, key: str, value: Any) -> None:
        if key not in MUTABLE_SCHEMA:
            raise KeyError(f"不允许修改的配置项: {key}")
        t = MUTABLE_SCHEMA[key]
        with self._lock:
            try:
                if t is bool:
                    if isinstance(value, str):
                        value = value.strip().lower() in ("1", "true", "yes", "on")
                    else:
                        value = bool(value)
                elif t is int:
                    value = int(value)
                elif t is float:
                    value = float(value)
                elif t is str:
                    value = "" if value is None else str(value).strip()
            except Exception as e:
                raise ValueError(f"配置项 {key} 类型错误: {e}")
            self._data[key] = value

    def update(self, items: Dict[str, Any]) -> None:
        for k, v in items.items():
            self.set(k, v)

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def reset(self) -> None:
        with self._lock:
            self._data = {}
            self.save()


runtime_store = RuntimeStore(CONFIG_PATH)
