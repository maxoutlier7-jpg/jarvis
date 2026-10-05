"""Roteamento estrito Gemini/Groq, retry classificado e tools controladas."""

import json
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.cache import ResponseCache
from core.config import config
from core.tokens import TokenTracker, estimate_tokens
from plugins import (
    execute_tool,
    gemini_function_declarations,
    openai_tool_definitions,
)


class ProviderError(RuntimeError):
    """Erro associado ao provider selecionado, sem fallback entre providers."""

    def __init__(self, provider: str, cause: Exception):
        self.provider = provider
        self.cause = cause
        super().__init__(f"{provider}: {cause}")


@dataclass
class LLMResult:
    """Resposta completa de uma chamada, com métricas de tokens."""

    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False


class LLM:
    """Camada unificada para Gemini e Groq, com seleção de provider persistente."""

    RETRYABLE_STATUS_CODES = (408, 429, 500, 502, 503, 504)
    AUTH_STATUS_CODES = (401, 403)

    def __init__(self):
        self.provider = config.DEFAULT_PROVIDER
        self._gemini_client = None
        self._groq_client = None
        self._setup()
        self.tracker = TokenTracker(config.TOKENS_PER_DAY, config.USAGE_FILE)
        self.cache = ResponseCache(
            ttl_seconds=config.CACHE_TTL_HOURS * 3600.0,
            max_entries=config.CACHE_MAX_ENTRIES,
        )
        # Não troque o provider automaticamente se sua chave/cliente estiver ausente.

    def _setup(self) -> None:
        if config.GEMINI_API_KEY:
            try:
                from google import genai

                self._gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception as exc:
                print(f"[Aviso] Gemini não pôde ser inicializado: {exc}")
        if config.GROQ_API_KEY:
            try:
                from groq import Groq

                self._groq_client = Groq(api_key=config.GROQ_API_KEY)
            except Exception as exc:
                print(f"[Aviso] Groq não pôde ser inicializado: {exc}")

    def available_providers(self) -> List[str]:
        providers: List[str] = []
        if self._gemini_client is not None:
            providers.append("gemini")
        if self._groq_client is not None:
            providers.append("groq")
        return providers

    def set_provider(self, provider: str) -> bool:
        provider = provider.strip().lower()
        if provider not in {"gemini", "groq"} or provider not in self.available_providers():
            return False
        self.provider = provider
        return True

    def _primary_model(self) -> str:
        return config.GEMINI_MODEL if self.provider == "gemini" else config.GROQ_MODEL

    @staticmethod
    def _obj_get(obj: Any, name: str, default: Any = None) -> Any:
        return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)

    @classmethod
    def _status_code(cls, exc: Exception) -> Optional[int]:
        for obj, attribute in (
            (exc, "status_code"),
            (exc, "code"),
            (getattr(exc, "response", None), "status_code"),
        ):
            value = getattr(obj, attribute, None) if obj is not None else None
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())
        return None

    @classmethod
    def _is_auth_error(cls, exc: Exception) -> bool:
        status = cls._status_code(exc)
        text = str(exc).lower()
        markers = (
            "invalid api key", "api key not valid", "api_key_invalid", "unauthorized",
            "authentication failed", "invalid authentication", "permission denied",
        )
        return status in cls.AUTH_STATUS_CODES or any(marker in text for marker in markers)

    @classmethod
    def _is_daily_quota_error(cls, exc: Exception) -> bool:
        text = str(exc).lower()
        explicit_daily = any(
            marker in text
            for marker in (
                "daily quota", "quota per day", "per day quota", "daily limit",
                "requests per day", "tokens per day", "per_day", "daily exhausted",
                "quota/day", "limit per day",
            )
        )
        quota_language = any(
            marker in text
            for marker in (
                "quota exceeded", "quota has been exceeded", "quota exhausted",
                "billing account", "free tier quota", "current quota",
            )
        )
        explicit_short_window = any(
            marker in text
            for marker in (
                "per minute", "per-minute", "per second", "per-second",
                "requests/minute", "tokens/minute", "rate limit", "too many requests",
                "retry-after", "retry after", "retry in", "retry_delay", "retry delay",
            )
        )
        return explicit_daily or (quota_language and not explicit_short_window)

    @classmethod
    def _is_retryable_error(cls, exc: Exception) -> bool:
        """Retenta só falhas transitórias; não interpreta qualquer texto como status."""
        if cls._is_auth_error(exc) or cls._is_daily_quota_error(exc):
            return False
        status = cls._status_code(exc)
        if status in cls.RETRYABLE_STATUS_CODES:
            return True
        if status is not None:
            return False
        if isinstance(exc, (TimeoutError, ConnectionError)):
            return True
        text = str(exc).lower()
        # Só aceite códigos textuais com rótulo explícito; um 429 citado no
        # conteúdo da mensagem não caracteriza, por si só, erro transitório.
        if re.search(
            r"\b(?:(?:http(?:/\d(?:\.\d)?)?\s+(?:status\s+)?)|"
            r"(?:status(?:_code)?[ :=]+)|(?:error code[ :=]+))"
            r"(?:408|429|500|502|503|504)\b",
            text,
        ):
            return True
        return any(
            marker in text
            for marker in (
                "timed out", "timeout", "deadline exceeded", "temporarily unavailable",
                "connection reset", "connection refused", "server disconnected",
                "service unavailable", "bad gateway", "internal server error",
            )
        )

    @classmethod
    def _is_fatal_provider_error(cls, exc: Exception) -> bool:
        """Erros que não melhoram trocando modelo ou repetindo a mesma cota."""
        return cls._is_auth_error(exc) or cls._is_daily_quota_error(exc)

    def _with_retry(self, operation, provider: str):
        last_error: Optional[Exception] = None
        max_retries = max(0, int(getattr(config, "MAX_RETRIES", 2)))
        base_delay = max(0.0, float(getattr(config, "RETRY_BASE_SECONDS", 1.0)))
        for attempt in range(max_retries + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries or not self._is_retryable_error(exc):
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, min(0.5, base_delay))
                print(
                    f"[Aviso] {provider} temporariamente indisponível. "
                    f"Nova tentativa {attempt + 1}/{max_retries} em {delay:.1f}s..."
                )
                time.sleep(delay)
        if last_error is None:
            last_error = RuntimeError("Falha desconhecida")
        raise last_error  # pragma: no cover

    def _trim_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Trunca por turnos completos, sem cortar par user/assistant."""
        budget = config.CONTEXT_TOKEN_BUDGET
        turns: List[List[Dict[str, str]]] = []
        index = 0
        while index < len(history):
            current = history[index]
            if current.get("role") != "user":
                index += 1
                continue
            turn = [current]
            if index + 1 < len(history) and history[index + 1].get("role") == "assistant":
                turn.append(history[index + 1])
                index += 2
            else:
                index += 1
            turns.append(turn)

        selected: List[List[Dict[str, str]]] = []
        total = 0
        for turn in reversed(turns):
            cost = sum(estimate_tokens(m.get("content", "")) for m in turn)
            if total + cost > budget:
                break
            selected.append(turn)
            total += cost
        return [message for turn in reversed(selected) for message in turn]

    def chat(self, user_message: str, history: List[Dict[str, str]]) -> LLMResult:
        """Chama exclusivamente o provider selecionado e registra sucessos."""
        if not user_message.strip():
            raise ValueError("Digite uma mensagem para o Jarvis.")
        providers = self.available_providers()
        if not providers:
            raise ProviderError(
                self.provider,
                RuntimeError(
                    "Nenhuma API está configurada. Configure GEMINI_API_KEY ou "
                    "GROQ_API_KEY no .env."
                ),
            )
        if self.provider not in providers:
            raise ProviderError(
                self.provider,
                RuntimeError(
                    f"O provedor selecionado ({self.provider}) não está disponível. "
                    f"Disponíveis: {', '.join(providers)}"
                ),
            )

        history = self._trim_history(history)
        cache_enabled = config.CACHE_MAX_ENTRIES > 0 and config.CACHE_TTL_HOURS > 0
        primary_model = self._primary_model()
        cache_key = ""
        if cache_enabled:
            cache_key = self.cache.make_key(
                self.provider,
                primary_model,
                user_message,
                history,
                system_prompt=config.SYSTEM_PROMPT,
            )
            cached_text = self.cache.get(cache_key)
            if cached_text is not None:
                self.tracker.record_cache_hit()
                return LLMResult(
                    text=cached_text,
                    provider=self.provider,
                    model=primary_model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cached=True,
                )

        estimated = estimate_tokens(config.SYSTEM_PROMPT) + estimate_tokens(user_message)
        estimated += sum(estimate_tokens(m.get("content", "")) for m in history)
        self.tracker.enforce_budget(extra=estimated + config.MAX_OUTPUT_TOKENS)

        # Despacho deliberadamente explícito: nenhum caminho chama o outro SDK.
        try:
            if self.provider == "gemini":
                result = self._chat_gemini(user_message, history)
            elif self.provider == "groq":
                result = self._chat_groq(user_message, history)
            else:  # proteger contra estado externo corrompido
                raise RuntimeError(f"Provedor desconhecido: {self.provider}")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.provider, exc) from exc

        text, model, prompt_tokens, completion_tokens = result
        # Só uma resposta final válida é gravada; erros e tool intermediárias não.
        self.tracker.record(self.provider, model, prompt_tokens, completion_tokens)
        if cache_enabled:
            # Armazene sob o modelo que de fato respondeu. Se houve fallback,
            # uma resposta dele nunca será servida como se viesse do primário.
            response_key = self.cache.make_key(
                self.provider,
                model,
                user_message,
                history,
                system_prompt=config.SYSTEM_PROMPT,
            )
            self.cache.set(response_key, text)
        return LLMResult(
            text=text,
            provider=self.provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    @staticmethod
    def _gemini_history(history: List[Dict[str, str]]):
        from google.genai import types

        result = []
        for message in history:
            role = "user" if message.get("role") == "user" else "model"
            result.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message.get("content", ""))],
                )
            )
        return result

    @staticmethod
    def _usage_value(usage: Any, attribute: str) -> int:
        return max(0, int(getattr(usage, attribute, 0) or 0)) if usage else 0

    @classmethod
    def _gemini_function_calls(cls, response: Any) -> list:
        calls = getattr(response, "function_calls", None)
        if calls:
            return list(calls)
        candidates = getattr(response, "candidates", None) or []
        found = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                call = getattr(part, "function_call", None)
                if call:
                    found.append(call)
        return found

    def _chat_gemini(
        self, user_message: str, history: List[Dict[str, str]]
    ) -> Tuple[str, str, int, int]:
        if self._gemini_client is None:
            raise RuntimeError("Cliente Gemini não está disponível")
        from google.genai import types

        last_error: Optional[Exception] = None
        models = list(dict.fromkeys(config.GEMINI_MODELS))
        for model in models:
            try:
                declarations = [
                    types.FunctionDeclaration(**item)
                    for item in gemini_function_declarations()
                ]
                tool_config = [types.Tool(function_declarations=declarations)] if declarations else None
                generate_config = types.GenerateContentConfig(
                    system_instruction=config.SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=config.MAX_OUTPUT_TOKENS,
                    tools=tool_config,
                )
                chat = self._gemini_client.chats.create(
                    model=model,
                    history=self._gemini_history(history),
                    config=generate_config,
                )
                prompt_tokens = 0
                completion_tokens = 0
                response = None
                message: Any = user_message
                max_rounds = max(1, int(getattr(config, "MAX_TOOL_ROUNDS", 4)))
                for round_index in range(max_rounds + 1):
                    response = self._with_retry(
                        lambda message=message: chat.send_message(message=message),
                        f"Gemini ({model})",
                    )
                    usage = getattr(response, "usage_metadata", None)
                    prompt_tokens += self._usage_value(usage, "prompt_token_count")
                    completion_tokens += self._usage_value(usage, "candidates_token_count")
                    calls = self._gemini_function_calls(response)
                    if not calls:
                        text = getattr(response, "text", None)
                        if not text:
                            raise RuntimeError("Gemini retornou uma resposta vazia")
                        if model != config.GEMINI_MODEL:
                            print(
                                f"[Aviso] Modelo Gemini principal {config.GEMINI_MODEL} falhou; "
                                f"usando fallback Gemini {model}."
                            )
                        return text, model, prompt_tokens, completion_tokens
                    if round_index >= max_rounds:
                        raise RuntimeError("Gemini excedeu o limite de ciclos de ferramentas")
                    function_parts = []
                    for call in calls:
                        name = getattr(call, "name", "") or ""
                        args = getattr(call, "args", {}) or {}
                        result = execute_tool(name, args)
                        payload = {"result": result.content, "is_error": result.is_error}
                        function_parts.append(
                            types.Part.from_function_response(name=result.name, response=payload)
                        )
                    message = function_parts
            except Exception as exc:
                last_error = exc
                if self._is_fatal_provider_error(exc):
                    raise
                continue
        if last_error is None:
            last_error = RuntimeError("Gemini falhou sem erro conhecido")
        raise last_error

    def _chat_groq(
        self, user_message: str, history: List[Dict[str, str]]
    ) -> Tuple[str, str, int, int]:
        if self._groq_client is None:
            raise RuntimeError("Cliente Groq não está disponível")
        messages: List[Dict[str, Any]] = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        tools = openai_tool_definitions()
        max_rounds = max(1, int(getattr(config, "MAX_TOOL_ROUNDS", 4)))
        last_error: Optional[Exception] = None

        for model in list(dict.fromkeys(config.GROQ_MODELS)):
            try:
                model_messages = [dict(message) for message in messages]
                prompt_tokens = 0
                completion_tokens = 0
                for round_index in range(max_rounds + 1):
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": model_messages,
                        "max_tokens": config.MAX_OUTPUT_TOKENS,
                    }
                    if tools and round_index < max_rounds:
                        kwargs["tools"] = tools
                        kwargs["tool_choice"] = "auto"
                    completion = self._with_retry(
                        lambda kwargs=kwargs: self._groq_client.chat.completions.create(**kwargs),
                        f"Groq ({model})",
                    )
                    usage = getattr(completion, "usage", None)
                    prompt_tokens += self._usage_value(usage, "prompt_tokens")
                    completion_tokens += self._usage_value(usage, "completion_tokens")
                    choices = getattr(completion, "choices", None) or []
                    if not choices:
                        raise RuntimeError("Groq não retornou escolhas na resposta")
                    message = getattr(choices[0], "message", None)
                    calls = getattr(message, "tool_calls", None) or []
                    if not calls:
                        text = getattr(message, "content", None)
                        if not text:
                            raise RuntimeError("Groq retornou uma resposta vazia")
                        if model != config.GROQ_MODEL:
                            print(
                                f"[Aviso] Modelo Groq principal {config.GROQ_MODEL} falhou; "
                                f"usando fallback Groq {model}."
                            )
                        return text, model, prompt_tokens, completion_tokens
                    if round_index >= max_rounds:
                        raise RuntimeError("Groq excedeu o limite de ciclos de ferramentas")

                    assistant_calls = []
                    tool_results = []
                    for call in calls:
                        call_id = self._obj_get(call, "id", "") or ""
                        function = self._obj_get(call, "function", {}) or {}
                        name = self._obj_get(function, "name", "") or ""
                        raw_arguments = self._obj_get(function, "arguments", "{}") or "{}"
                        try:
                            arguments = (
                                raw_arguments if isinstance(raw_arguments, dict)
                                else json.loads(raw_arguments)
                            )
                        except (TypeError, ValueError):
                            arguments = None
                        result = execute_tool(name, arguments)
                        assistant_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": raw_arguments if isinstance(raw_arguments, str)
                                    else json.dumps(raw_arguments, ensure_ascii=False),
                                },
                            }
                        )
                        tool_results.append((call_id, result.content))
                    model_messages.append(
                        {"role": "assistant", "content": None, "tool_calls": assistant_calls}
                    )
                    for call_id, content in tool_results:
                        model_messages.append(
                            {"role": "tool", "tool_call_id": call_id, "content": content}
                        )
                    # Loop vuelve ao modelo com tool call e resultado registrados.
            except Exception as exc:
                last_error = exc
                if self._is_fatal_provider_error(exc):
                    raise
                continue
        if last_error is None:
            last_error = RuntimeError("Groq falhou sem erro conhecido")
        raise last_error
