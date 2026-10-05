import random
import time
from typing import Dict, List

from core.config import config


class ProviderError(RuntimeError):
    """Erro de um provedor específico, sem fallback silencioso para outro provedor."""

    def __init__(self, provider: str, cause: Exception):
        self.provider = provider
        self.cause = cause
        super().__init__(f"{provider}: {cause}")


class LLM:
    """Camada unificada para Gemini e Groq, com roteamento estrito."""

    MAX_RETRIES = 3
    RETRYABLE_STATUS_CODES = (408, 429, 500, 502, 503, 504)

    def __init__(self):
        self.provider = config.DEFAULT_PROVIDER
        self._gemini_client = None
        self._groq_client = None
        self._setup()

        if self.provider not in self.available_providers():
            available = self.available_providers()
            if available:
                self.provider = available[0]

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
        if self._gemini_client:
            providers.append("gemini")
        if self._groq_client:
            providers.append("groq")
        return providers

    def set_provider(self, provider: str) -> bool:
        provider = provider.strip().lower()
        if provider not in {"gemini", "groq"}:
            return False
        if provider not in self.available_providers():
            return False
        self.provider = provider
        return True

    @staticmethod
    def _gemini_history(history: List[Dict[str, str]]):
        from google.genai import types

        result = []
        for message in history:
            role = "user" if message["role"] == "user" else "model"
            result.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message["content"])],
                )
            )
        return result

    @classmethod
    def _is_retryable_error(cls, exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code in cls.RETRYABLE_STATUS_CODES:
            return True

        text = str(exc).upper()
        return any(
            marker in text
            for marker in (
                "503",
                "UNAVAILABLE",
                "429",
                "RESOURCE_EXHAUSTED",
                "500",
                "INTERNAL",
                "502",
                "BAD GATEWAY",
                "504",
                "DEADLINE_EXCEEDED",
                "408",
                "TIMEOUT",
            )
        )

    def _with_retry(self, operation, provider: str):
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt >= self.MAX_RETRIES or not self._is_retryable_error(exc):
                    raise
                delay = (2**attempt) + random.uniform(0, 0.5)
                print(
                    f"[Aviso] {provider} temporariamente indisponível. "
                    f"Nova tentativa em {delay:.1f}s..."
                )
                time.sleep(delay)
        raise last_error  # pragma: no cover

    def chat(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """Conversa usando EXCLUSIVAMENTE o provedor selecionado pelo usuário.

        Isso impede que uma falha do Groq caia silenciosamente no Gemini, ou vice-versa.
        O provedor só muda quando o usuário usa /provider ou quando o programa inicia
        e precisa escolher o primeiro provedor realmente disponível.
        """
        if not user_message.strip():
            return "Digite uma mensagem para o Jarvis."

        providers = self.available_providers()
        if not providers:
            raise ProviderError(
                "nenhum",
                RuntimeError(
                    "Nenhuma API está configurada. Configure GEMINI_API_KEY ou GROQ_API_KEY no .env."
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

        try:
            if self.provider == "gemini":
                return self._chat_gemini(user_message, history).strip()
            return self._with_retry(
                lambda: self._chat_groq(user_message, history), "Groq"
            ).strip()
        except Exception as exc:
            raise ProviderError(self.provider, exc) from exc

    def _chat_gemini(self, user_message: str, history: List[Dict[str, str]]) -> str:
        if not self._gemini_client:
            raise RuntimeError("Cliente Gemini não está disponível")

        from google.genai import types
        last_error = None

        for model in config.GEMINI_MODELS:
            try:
                chat = self._gemini_client.chats.create(
                    model=model,
                    history=self._gemini_history(history),
                    config=types.GenerateContentConfig(
                        system_instruction=config.SYSTEM_PROMPT,
                        temperature=0.7,
                    ),
                )
                response = self._with_retry(
                    lambda: chat.send_message(message=user_message),
                    f"Gemini ({model})",
                )
                text = getattr(response, "text", None)
                if not text:
                    raise RuntimeError("Gemini retornou uma resposta vazia")
                if model != config.GEMINI_MODEL:
                    print(f"[Aviso] Gemini principal indisponível. Usando {model}.")
                return text
            except Exception as exc:
                last_error = exc
                continue

        raise last_error  # pragma: no cover

    def _chat_groq(self, user_message: str, history: List[Dict[str, str]]) -> str:
        if not self._groq_client:
            raise RuntimeError("Cliente Groq não está disponível")

        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        completion = self._groq_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )

        if not completion.choices:
            raise RuntimeError("Groq não retornou escolhas na resposta")

        text = completion.choices[0].message.content
        if not text:
            raise RuntimeError("Groq retornou uma resposta vazia")
        return text
