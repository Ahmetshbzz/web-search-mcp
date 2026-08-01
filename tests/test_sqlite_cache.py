import pytest

from web_search_mcp.cache import SQLiteTTLCache


@pytest.mark.asyncio
async def test_sqlite_cache_set_get_list(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache = SQLiteTTLCache(str(db_file))

    # Get non-existent
    assert await cache.get("key1") is None

    # Set and Get valid item
    await cache.set("key1", {"data": 123}, ttl_seconds=10)
    res = await cache.get("key1")
    assert res == {"data": 123}

    # List keys
    keys = await cache.list_keys()
    assert "key1" in keys

    # Expiry
    await cache.set("key2", "expired", ttl_seconds=-1)
    assert await cache.get("key2") is None

    await cache.close()


@pytest.mark.asyncio
async def test_sqlite_cache_persistent_connection(tmp_path):
    """Bağlantı yeniden kullanılır; close() sonrası lazy reconnect çalışır."""
    db_file = tmp_path / "test_cache_persist.db"
    cache = SQLiteTTLCache(str(db_file))

    await cache.set("a", 1, ttl_seconds=10)
    conn1 = cache._get_conn()
    await cache.set("b", 2, ttl_seconds=10)
    conn2 = cache._get_conn()
    assert conn1 is conn2  # aynı kalıcı bağlantı

    await cache.close()
    assert cache._conn is None

    # close() sonrası ilk erişimde bağlantı yeniden açılır
    assert await cache.get("a") == 1
    await cache.close()
