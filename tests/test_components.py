import pytest

from core.cache import ResponseCache
from core.memory import Memory
from core.tokens import TokenTracker
from plugins import execute_tool, get_plugin, list_plugins, register


def test_memory_limit_is_even_and_keeps_complete_turns():
    memory = Memory(max_messages=5)
    for i in range(5):
        memory.add_exchange(f"u{i}", f"a{i}")
    history = memory.get_history()
    assert memory.max_messages == 4
    assert len(history) == 4
    assert [(history[i]["role"], history[i + 1]["role"]) for i in range(0, 4, 2)] == [
        ("user", "assistant"), ("user", "assistant")
    ]
    assert history[0]["content"] == "u3"
    assert history[-1]["content"] == "a4"


def test_memory_never_keeps_orphan_assistant_at_start():
    memory = Memory(max_messages=2)
    memory.add("assistant", "órfã")
    assert memory.get_history() == []
    memory.add_exchange("pergunta", "resposta")
    assert [item["role"] for item in memory.get_history()] == ["user", "assistant"]


def test_cache_identity_separates_provider_model_and_roles():
    history_user = [{"role": "user", "content": "context"}]
    history_assistant = [{"role": "assistant", "content": "context"}]
    base = ResponseCache.make_key("groq", "openai/gpt-oss-20b", "oi", history_user)
    assert base != ResponseCache.make_key("gemini", "openai/gpt-oss-20b", "oi", history_user)
    assert base != ResponseCache.make_key("groq", "other-model", "oi", history_user)
    assert base != ResponseCache.make_key("groq", "openai/gpt-oss-20b", "oi", history_assistant)
    assert base != ResponseCache.make_key(
        "groq", "openai/gpt-oss-20b", "oi", history_user, system_prompt="novo"
    )


def test_cache_evicts_expired_entries_when_inserting():
    cache = ResponseCache(ttl_seconds=0.03, max_entries=2)
    cache.set("expired", "old")
    import time
    time.sleep(0.04)
    cache.set("fresh", "new")
    assert len(cache) == 1
    assert cache.get("expired") is None
    assert cache.get("fresh") == "new"


def test_token_tracker_clamps_negative_and_records_success_once(tmp_path):
    path = tmp_path / "nested" / "usage.json"
    tracker = TokenTracker(100, str(path))
    tracker.record("groq", "model", -5, 7)
    summary = tracker.summary()
    assert summary["session_prompt"] == 0
    assert summary["session_completion"] == 7
    assert summary["requests"] == 1
    restored = TokenTracker(100, str(path))
    assert restored.used_today() == 7
    assert restored.summary()["requests"] == 0


def test_tool_registry_normalizes_and_validates_schema(monkeypatch):
    import plugins

    monkeypatch.setattr(plugins, "PLUGINS", dict(plugins.PLUGINS))
    monkeypatch.setattr(plugins, "TOOL_SCHEMAS", dict(plugins.TOOL_SCHEMAS))
    monkeypatch.setattr(plugins, "TOOL_DESCRIPTIONS", dict(plugins.TOOL_DESCRIPTIONS))
    schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }
    register("  Test Tool ", lambda value: value, schema=schema)
    assert get_plugin("test_tool")("ok") == "ok"
    assert "test_tool" in list_plugins()
    with pytest.raises(ValueError):
        register("bad schema", lambda: None, schema={"type": "array"})
    with pytest.raises(ValueError):
        register("bad_required", lambda: None, schema={"type": "object", "properties": {}, "required": ["x"]})
    assert get_plugin("bad_required") is None
    with pytest.raises(ValueError):
        register("bad_property", lambda x: x, schema={"type": "object", "properties": {"x": "string"}})
    assert get_plugin("bad_property") is None


def test_calculator_is_safe_and_returns_errors_without_crashing():
    result = execute_tool("calculator", {"expression": "(2 + 3) * 4"})
    assert result.content == "20"
    assert not result.is_error
    blocked = execute_tool("calculator", {"expression": "__import__('os').system('id')"})
    assert blocked.is_error
    assert "não permitida" in blocked.content
    invalid = execute_tool("calculator", {"expression": "1 / 0"})
    assert invalid.is_error
    wrong_type = execute_tool("calculator", {"expression": 12})
    assert wrong_type.is_error
    extra = execute_tool("calculator", {"expression": "2", "untrusted": "x"})
    assert extra.is_error
    assert execute_tool("missing_tool", {}).is_error


def test_registered_tools_include_web_search():
    from plugins import TOOL_SCHEMAS

    assert "web_search" in list_plugins()
    assert TOOL_SCHEMAS["web_search"]["required"] == ["query"]
