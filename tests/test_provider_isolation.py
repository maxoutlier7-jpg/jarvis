import sys
import types as pytypes
from types import SimpleNamespace

import pytest

from core.cache import ResponseCache
from core.config import config
from core.llm import LLM, ProviderError
from core.tokens import TokenTracker


class APIError(RuntimeError):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def make_llm(provider="gemini", gemini_client=None, groq_client=None):
    llm = LLM.__new__(LLM)
    llm.provider = provider
    llm._gemini_client = gemini_client
    llm._groq_client = groq_client
    llm.tracker = TokenTracker(0, "")
    llm.cache = ResponseCache(0, 0)
    return llm


def groq_answer(text="resposta"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=[]))],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
    )


def install_fake_genai(monkeypatch):
    def factory(**kwargs):
        return SimpleNamespace(**kwargs)

    part = SimpleNamespace(
        from_text=lambda **kwargs: factory(**kwargs),
        from_function_response=lambda **kwargs: factory(**kwargs),
    )
    fake_types = SimpleNamespace(
        Content=factory,
        Part=part,
        FunctionDeclaration=factory,
        Tool=factory,
        GenerateContentConfig=factory,
    )
    google = pytypes.ModuleType("google")
    google.__path__ = []
    genai = pytypes.ModuleType("google.genai")
    genai.types = fake_types
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    return fake_types


def setup_no_cache(monkeypatch):
    monkeypatch.setattr(config, "CACHE_TTL_HOURS", 0)
    monkeypatch.setattr(config, "CACHE_MAX_ENTRIES", 0)
    monkeypatch.setattr(config, "TOKENS_PER_DAY", 0)
    monkeypatch.setattr(config, "MAX_TOOL_ROUNDS", 3)
    monkeypatch.setattr(config, "MAX_OUTPUT_TOKENS", 256)


def test_set_provider_groq_never_calls_gemini_even_if_groq_fails(monkeypatch):
    """A rota real de chat chama o SDK Groq e nunca o cliente Gemini."""
    setup_no_cache(monkeypatch)
    monkeypatch.setattr(config, "GROQ_MODEL", "groq-primary")
    monkeypatch.setattr(config, "GROQ_MODELS", ["groq-primary", "groq-fallback"])

    class GroqCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            raise APIError("invalid API key", 401)

    groq_api = GroqCompletions()

    class GeminiClient:
        def __init__(self):
            self.calls = 0

    gemini_api = GeminiClient()
    llm = make_llm(
        "gemini",
        gemini_client=gemini_api,
        groq_client=SimpleNamespace(chat=SimpleNamespace(completions=groq_api)),
    )
    assert llm.set_provider("groq") is True

    with pytest.raises(ProviderError) as caught:
        llm.chat("oi", [])

    assert caught.value.provider == "groq"
    assert "invalid API key" in str(caught.value.cause)
    assert len(groq_api.calls) == 1
    assert groq_api.calls[0]["model"] == "groq-primary"
    assert gemini_api.calls == 0
    assert llm.provider == "groq"
    assert llm.tracker.summary()["requests"] == 0


def test_gemini_failure_never_calls_groq(monkeypatch):
    setup_no_cache(monkeypatch)
    install_fake_genai(monkeypatch)
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["gemini-primary", "gemini-fallback"])

    class GeminiChat:
        def send_message(self, **kwargs):
            raise APIError("invalid API key", 401)

    class GeminiChats:
        def create(self, **kwargs):
            return GeminiChat()

    class GroqCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return groq_answer()

    groq_api = GroqCompletions()
    llm = make_llm(
        "gemini",
        gemini_client=SimpleNamespace(chats=GeminiChats()),
        groq_client=SimpleNamespace(chat=SimpleNamespace(completions=groq_api)),
    )

    with pytest.raises(ProviderError) as caught:
        llm.chat("oi", [])

    assert caught.value.provider == "gemini"
    assert groq_api.calls == 0
    assert llm.provider == "gemini"


def test_provider_selection_requires_available_client(monkeypatch):
    llm = make_llm("gemini", gemini_client=object(), groq_client=object())
    assert llm.set_provider(" GROQ ") is True
    assert llm.provider == "groq"
    assert llm.set_provider("gemini") is True
    assert llm.provider == "gemini"
    assert llm.set_provider("openai") is False
    assert llm.provider == "gemini"

    unavailable = make_llm("groq", gemini_client=object(), groq_client=None)
    assert unavailable.set_provider("groq") is False
    assert unavailable.provider == "groq"


def test_groq_model_fallback_stays_within_groq(monkeypatch):
    setup_no_cache(monkeypatch)
    monkeypatch.setattr(config, "GROQ_MODEL", "groq-primary")
    monkeypatch.setattr(config, "GROQ_MODELS", ["groq-primary", "groq-fallback"])

    class GroqCompletions:
        def __init__(self):
            self.models = []

        def create(self, **kwargs):
            self.models.append(kwargs["model"])
            if kwargs["model"] == "groq-primary":
                raise APIError("model not found", 404)
            return groq_answer("fallback ok")

    class NeverGemini:
        calls = 0

    groq_api = GroqCompletions()
    gemini = NeverGemini()
    llm = make_llm("groq", gemini, SimpleNamespace(chat=SimpleNamespace(completions=groq_api)))
    result = llm.chat("oi", [])
    assert result.text == "fallback ok"
    assert result.provider == "groq"
    assert result.model == "groq-fallback"
    assert groq_api.models == ["groq-primary", "groq-fallback"]
    assert gemini.calls == 0
    assert llm.provider == "groq"


def test_gemini_model_fallback_stays_within_gemini(monkeypatch):
    setup_no_cache(monkeypatch)
    install_fake_genai(monkeypatch)
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["gemini-primary", "gemini-fallback"])

    class GeminiChat:
        def __init__(self, model):
            self.model = model

        def send_message(self, **kwargs):
            if self.model == "gemini-primary":
                raise APIError("model not found", 404)
            return SimpleNamespace(
                text="fallback ok",
                function_calls=[],
                usage_metadata=SimpleNamespace(prompt_token_count=2, candidates_token_count=3),
            )

    class GeminiChats:
        def create(self, model, **kwargs):
            return GeminiChat(model)

    class GroqCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return groq_answer()

    groq_api = GroqCompletions()
    llm = make_llm(
        "gemini",
        SimpleNamespace(chats=GeminiChats()),
        SimpleNamespace(chat=SimpleNamespace(completions=groq_api)),
    )
    result = llm.chat("oi", [])
    assert result.text == "fallback ok"
    assert result.provider == "gemini"
    assert result.model == "gemini-fallback"
    assert groq_api.calls == 0


def test_daily_quota_does_not_retry_or_try_another_model(monkeypatch):
    setup_no_cache(monkeypatch)
    monkeypatch.setattr(config, "GROQ_MODEL", "groq-primary")
    monkeypatch.setattr(config, "GROQ_MODELS", ["groq-primary", "groq-fallback"])
    monkeypatch.setattr(config, "MAX_RETRIES", 4)
    monkeypatch.setattr(config, "RETRY_BASE_SECONDS", 0)

    class GroqCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs["model"])
            raise APIError("Daily quota exceeded for this account", 429)

    api = GroqCompletions()
    llm = make_llm("groq", groq_client=SimpleNamespace(chat=SimpleNamespace(completions=api)))
    with pytest.raises(ProviderError) as caught:
        llm.chat("oi", [])
    assert caught.value.provider == "groq"
    assert api.calls == ["groq-primary"]
    assert llm.provider == "groq"


def test_transient_503_retries_with_backoff_then_succeeds(monkeypatch):
    setup_no_cache(monkeypatch)
    monkeypatch.setattr(config, "MAX_RETRIES", 2)
    monkeypatch.setattr(config, "RETRY_BASE_SECONDS", 0.25)
    sleeps = []
    monkeypatch.setattr("core.llm.time.sleep", sleeps.append)
    calls = []

    def operation():
        calls.append(1)
        if len(calls) < 2:
            raise APIError("server unavailable", 503)
        return "ok"

    llm = make_llm()
    assert llm._with_retry(operation, "Groq") == "ok"
    assert len(calls) == 2
    assert len(sleeps) == 1
    assert sleeps[0] >= 0.25


def test_retry_classifier_does_not_match_arbitrary_429_or_resource_exhausted_text():
    assert not LLM._is_retryable_error(RuntimeError("payload field 429 in user data"))
    assert not LLM._is_retryable_error(RuntimeError("RESOURCE_EXHAUSTED"))
    assert LLM._is_retryable_error(APIError("rate limited", 429))
    assert LLM._is_retryable_error(APIError("rate limit; retry in 2 seconds", 429))
    assert not LLM._is_daily_quota_error(APIError("rate limit; retry in 2 seconds", 429))
    assert LLM._is_daily_quota_error(APIError("quota exceeded for requests_per_day", 429))
    assert not LLM._is_retryable_error(APIError("invalid API key", 401))
    assert LLM._is_retryable_error(TimeoutError("network timed out"))


def test_groq_tool_call_executes_then_returns_to_model(monkeypatch):
    setup_no_cache(monkeypatch)
    monkeypatch.setattr(config, "GROQ_MODEL", "groq-primary")
    monkeypatch.setattr(config, "GROQ_MODELS", ["groq-primary"])

    class GroqCompletions:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 1:
                tool_call = SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(
                        name="calculator", arguments='{"expression":"2 + 2"}'
                    ),
                )
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))],
                    usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
                )
            return groq_answer("O resultado é 4.")

    api = GroqCompletions()
    llm = make_llm("groq", groq_client=SimpleNamespace(chat=SimpleNamespace(completions=api)))
    result = llm.chat("quanto é 2 + 2?", [])
    assert result.text == "O resultado é 4."
    assert len(api.requests) == 2
    messages = api.requests[1]["messages"]
    assert messages[-2]["role"] == "assistant"
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["content"] == "4"


def test_gemini_tool_call_executes_then_returns_to_model_without_groq(monkeypatch):
    setup_no_cache(monkeypatch)
    install_fake_genai(monkeypatch)
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(config, "GEMINI_MODELS", ["gemini-primary"])

    class GeminiChat:
        def __init__(self):
            self.messages = []

        def send_message(self, message):
            self.messages.append(message)
            if len(self.messages) == 1:
                return SimpleNamespace(
                    function_calls=[SimpleNamespace(name="calculator", args={"expression": "2 + 2"})],
                    text=None,
                    usage_metadata=SimpleNamespace(prompt_token_count=4, candidates_token_count=2),
                )
            return SimpleNamespace(
                function_calls=[],
                text="O resultado é 4.",
                usage_metadata=SimpleNamespace(prompt_token_count=3, candidates_token_count=3),
            )

    class GeminiChats:
        def __init__(self):
            self.chat = GeminiChat()

        def create(self, **kwargs):
            self.kwargs = kwargs
            return self.chat

    class NeverGroq:
        def create(self, **kwargs):
            raise AssertionError("Gemini não pode chamar Groq")

    chats = GeminiChats()
    llm = make_llm(
        "gemini",
        gemini_client=SimpleNamespace(chats=chats),
        groq_client=SimpleNamespace(chat=SimpleNamespace(completions=NeverGroq())),
    )
    result = llm.chat("quanto é 2 + 2?", [])

    assert result.text == "O resultado é 4."
    assert result.provider == "gemini"
    assert len(chats.chat.messages) == 2
    function_response = chats.chat.messages[1][0]
    assert function_response.name == "calculator"
    assert function_response.response["result"] == "4"
    assert not function_response.response["is_error"]
