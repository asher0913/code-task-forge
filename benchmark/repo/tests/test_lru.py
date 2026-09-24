import pytest

from tinylib.lru import LRUCache


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_missing_key_returns_default():
    assert LRUCache(2).get("x", 7) == 7


def test_evicts_oldest_when_full():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None and cache.get("b") == 2 and cache.get("c") == 3


def test_get_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
