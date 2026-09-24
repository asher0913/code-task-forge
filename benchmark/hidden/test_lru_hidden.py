from tinylib.lru import LRUCache


def test_put_on_existing_key_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 10


def test_capacity_one():
    cache = LRUCache(1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") is None and cache.get("b") == 2
    assert len(cache) == 1


def test_update_does_not_grow():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("a", 2)
    assert len(cache) == 1 and cache.get("a") == 2


def test_read_then_write_order():
    cache = LRUCache(3)
    for key in "abc":
        cache.put(key, key)
    cache.get("a")
    cache.put("b", "B")
    cache.put("d", "d")
    assert cache.get("c") is None
    assert [cache.get(k) for k in "abd"] == ["a", "B", "d"]
