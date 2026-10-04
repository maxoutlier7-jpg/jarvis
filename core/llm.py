from typing import Dict, List

from core.config import config


class LLM:
    """Camada unificada para Gemini e Groq, com fallback automático."""

    def __init__(self):
        self.provider = config.DEFAULT_PROVIDER
        self._gemini_client = None
        self._groq_client = None
        self._setup()

        # Se o provedor configurado não estiver disponível, usa outro automaticamente.
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
    def _history_text(history: List[Dict[str, str]]) -> str:
        if not history:
            return ""

        lines = ["Histórico recente da conversa:"]
        for message in history:
            role = "Usuário" if message["role"] == "user" else "Jarvis"
            lines.append(f"{role}: {message['content']}")
        return "\n".join(lines)

    def chat(self, user_message: str, history: List[Dict[str, str]]) -> str:
        if not user_message.strip():
            return "Digite uma mensagem para o Jarvis."

        providers = self.available_providers()
        if not providers:
            return (
                "Nenhuma API está configurada. Coloque GEMINI_API_KEY ou "
                "GROQ_API_KEY no arquivo .env e tente novamente."
            )

        # Tenta primeiro o provedor selecionado e depois o outro como fallback.
        order = [self.provider] + [p for p in providers if p != self.provider]
        last_error = None

        for provider in order:
            try:
                if provider == "gemini":
                    response = self._chat_gemini(user_message, history)
                else:
                    response = self._chat_groq(user_message, history)

                self.provider = provider
                return response.strip() or "O modelo não retornou texto."
            except Exception as exc:
                last_error = exc
                continue

        return f"Não consegui obter uma resposta do provedor de IA: {last_error}"

    def _chat_gemini(self, user_message: str, history: List[Dict[str, str]]) -> str:
        if not self._gemini_client:
            raise RuntimeError("Cliente Gemini não está disponível")

        history_text = self._history_text(history)
        prompt = user_message
        if history_text:
            prompt = f"{history_text}\n\nMensagem atual do usuário:\n{user_message}"

        from google.genai import types

        response = self._gemini_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
                temperature=0.7,
            ),
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini retornou uma resposta vazia")
        return text

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

        text = completion.choices[0].message.content
        if not text:
            raise RuntimeError("Groq retornou uma resposta vazia")
        return text
