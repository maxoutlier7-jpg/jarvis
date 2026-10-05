from core.llm import ProviderError


def test_provider_errors_are_not_saved_as_valid_memory(monkeypatch):
    import web

    class FakeTracker:
        def summary(self):
            return {
                "today_total": 0,
                "budget": 0,
                "session_total": 0,
                "session_prompt": 0,
                "session_completion": 0,
                "requests": 0,
                "cache_hits": 0,
                "remaining": None,
            }

    class FakeCache:
        def clear(self):
            pass

    class FailingLLM:
        provider = "groq"
        tracker = FakeTracker()
        cache = FakeCache()

        def set_provider(self, provider):
            self.provider = provider
            return True

        def chat(self, message, history):
            raise ProviderError("groq", RuntimeError("quota diária esgotada"))

    web.memory.clear()
    monkeypatch.setattr(web, "llm", FailingLLM())
    _message, visible_history, _usage = web.respond("oi", [], "groq")
    assert len(visible_history) == 2
    assert "Falha no provedor Groq" in visible_history[-1]["content"]
    assert web.memory.get_history() == []


def test_gradio_app_builds_with_installed_api():
    import web

    assert web.build_app() is not None
