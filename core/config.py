import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _list_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gemini").strip().lower()
    if DEFAULT_PROVIDER not in {"gemini", "groq"}:
        DEFAULT_PROVIDER = "gemini"

    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    GEMINI_FALLBACK_MODELS = _list_env(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.5-flash,gemini-3.1-flash-lite",
    )
    GEMINI_MODELS = list(dict.fromkeys([GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]))

    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
    MEMORY_MAX_MESSAGES = max(2, _int_env("MEMORY_MAX_MESSAGES", 30))

    SYSTEM_PROMPT = """Você é o Jarvis, um assistente de IA pessoal extremamente inteligente, prestativo e confiável.
Você fala português do Brasil de forma natural, clara e objetiva.
Você tem um toque de humor quando apropriado, inspirado no Jarvis do Homem de Ferro, sem fingir ser uma pessoa real.
Priorize respostas corretas, úteis e práticas. Se não souber algo, diga claramente e não invente.
Quando receber código, ajude a encontrar e corrigir erros e explique o necessário de forma objetiva.
"""


config = Config()
