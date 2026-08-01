import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import aiosqlite


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
    def __init__(self, db_path: str = "data/cache.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _init_db(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    async def get(self, key: str) -> Any | None:
        await self._init_db()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                val_json, expires_at = row
                if now > expires_at:
                    await db.execute("DELETE FROM cache WHERE key = ?", (key,))
                    await db.commit()
                    return None
                try:
                    return json.loads(val_json)
                except Exception:
                    return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self._init_db()
        expires_at = time.time() + ttl_seconds
        val_json = json.dumps(value)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO cache (key, value, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at
                """,
                (key, val_json, expires_at),
            )
            await db.commit()

    async def list_keys(self) -> list[str]:
        await self._init_db()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT key FROM cache WHERE expires_at > ?", (now,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]


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

