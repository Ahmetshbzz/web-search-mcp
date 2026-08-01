import asyncio
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class TTLCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_keys(self) -> list[str]:
        raise NotImplementedError


class SQLiteTTLCache(TTLCache):
    """SQLite-backed TTL cache.

    Optimizasyonlar:
    - Instance başına tek kalıcı bağlantı (operasyon başına connect/close yok).
    - WAL journal mode + NORMAL synchronous → hızlı okuma/yazma.
    - Her `_SWEEP_EVERY_SETS` yazmada expired kayıt temizliği → DB şişmez.
    - stdlib sqlite3 + asyncio.to_thread: aiosqlite'ın non-daemon worker
      thread'i process çıkışında asılı kalabildiği için tercih edilmedi.
      asyncio.Lock eşzamanlı to_thread erişimini serileştirir.
    """

    _SWEEP_EVERY_SETS = 50

    def __init__(self, db_path: str = "data/cache.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._writes_since_sweep = 0

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache (expires_at)")
            conn.commit()
            self._conn = conn
        return self._conn

    def _get_sync(self, key: str) -> Any | None:
        conn = self._get_conn()
        row = conn.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        val_json, expires_at = row
        if time.time() > expires_at:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None
        try:
            return json.loads(val_json)
        except Exception:
            return None

    def _set_sync(self, key: str, value: Any, ttl_seconds: int) -> None:
        conn = self._get_conn()
        expires_at = time.time() + ttl_seconds
        conn.execute(
            """
            INSERT INTO cache (key, value, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at
            """,
            (key, json.dumps(value), expires_at),
        )
        self._writes_since_sweep += 1
        if self._writes_since_sweep >= self._SWEEP_EVERY_SETS:
            self._writes_since_sweep = 0
            conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))
        conn.commit()

    def _list_keys_sync(self) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT key FROM cache WHERE expires_at > ?", (time.time(),)).fetchall()
        return [row[0] for row in rows]

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            return await asyncio.to_thread(self._get_sync, key)

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._set_sync, key, value, ttl_seconds)

    async def list_keys(self) -> list[str]:
        async with self._lock:
            return await asyncio.to_thread(self._list_keys_sync)

    async def close(self) -> None:
        async with self._lock:
            conn, self._conn = self._conn, None
        if conn is not None:
            await asyncio.to_thread(conn.close)


class MemoryTTLCache(TTLCache):
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            del self._items[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._items[key] = (time.time() + ttl_seconds, value)

    async def list_keys(self) -> list[str]:
        now = time.time()
        return [k for k, (exp, _) in self._items.items() if exp > now]
