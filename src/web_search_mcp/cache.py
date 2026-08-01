import threading
import time
from abc import ABC, abstractmethod


class TTLCache(ABC):
    @abstractmethod
    def get(self, key: str) -> object | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        raise NotImplementedError


class MemoryTTLCache(TTLCache):
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() > expires_at:
                del self._items[key]
                return None
            return value

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        with self._lock:
            self._items[key] = (time.monotonic() + ttl_seconds, value)
