import time

import pytest

from core.cache import ResponseCache
from core.config import config
from core.llm import LLM, ProviderError
from core.memory import Memory
from core.tokens import BudgetExceededError, TokenTracker, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_memory_trims_and_keeps_pairs():
    memory = Memory(max_messages=4)
    for i in range(10):
        memory.add("user", f"u{i}")
        memory.add("assistant", f"a{i}")
    history = memory.get_history()
    assert len(history) == 4
    assert history[0]["content"] == "u8"
    assert history[0]["role"] == "user"
    assert history[-1]["content"] == "a9"


def test_memory_rejects_invalid_role():
    memory = Memory(max_messages=4)
    with pytest.raises(ValueError):
        memory.add("system", "oi")


def test_tracker_budget_blocks_when_exceeded():
    tracker = TokenTracker(daily_budget=100, storage_path="")
    tracker.record("gemini", "m", 60, 0)
    tracker.enforce_budget(extra=10)
    tracker.record("gemini", "m", 40, 0)
    with pytest.raises(BudgetExceededError):
        tracker.enforce_budget(extra=10)


def test_tracker_unlimited_never_blocks():
    tracker = TokenTracker(daily_budget=0, storage_path="")
    tracker.record("groq", "m", 10**9, 0)
    tracker.enforce_budget(extra=10**9)


def test_tracker_persists_usage(tmp_path):
    path = tmp_path / "usage.json"
    t1 = TokenTracker(1000, str(path))
    t1.record("gemini", "m", 10, 5)
    t2 = TokenTracker(1000, str(path))
    assert t2.used_today() == 15
    summary = t2.summary()
    assert summary["budget"] == 1000
    assert summary["remaining"] == 985


def test_cache_roundtrip_and_ttl():
    cache = ResponseCache(ttl_seconds=0.05, max_entries=8)
    key = cache.make_key("gemini", "m", "oi", [])
    cache.set(key, "olá")
    assert cache.get(key) == "olá"
    time.sleep(0.06)
    assert cache.get(key) is None


def test_cache_key_depends_on_history():
    k1 = ResponseCache.make_key("gemini", "m", "oi", [{"role": "user", "content": "a"}])
    k2 = ResponseCache.make_key("gemini", "m", "oi", [{"role": "user", "content": "b"}])
    assert k1 != k2


def test_cache_evicts_oldest():
    cache = ResponseCache(ttl_seconds=60, max_entries=2)
    for i in range(3):
        key = cache.make_key("p", "m", f"q{i}", [])
        cache.set(key, f"r{i}")
    assert cache.get(cache.make_key("p", "m", "q0", [])) is None
    assert cache.get(cache.make_key("p", "m", "q2", [])) == "r2"


def test_trim_history_respects_budget_and_starts_with_user():
    llm = LLM.__new__(LLM)
    history = []
    for _ in range(50):
        history.append({"role": "user", "content": "x" * 200})
        history.append({"role": "assistant", "content": "y" * 200})
    trimmed = llm._trim_history(history)
    assert trimmed[0]["role"] == "user"
    total = sum(estimate_tokens(m["content"]) for m in trimmed)
    assert total <= config.CONTEXT_TOKEN_BUDGET


def test_llm_without_keys_raises_provider_error():
    llm = LLM.__new__(LLM)
    llm.provider = "gemini"
    llm._gemini_client = None
    llm._groq_client = None
    llm.tracker = TokenTracker(0, "")
    llm.cache = ResponseCache(0, 0)
    with pytest.raises(ProviderError):
        llm.chat("oi", [])
