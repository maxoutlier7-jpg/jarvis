import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gemini").strip().lower()
    if DEFAULT_PROVIDER not in {"gemini", "groq"}:
        DEFAULT_PROVIDER = "gemini"

    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    MEMORY_MAX_MESSAGES = max(2, _int_env("MEMORY_MAX_MESSAGES", 30))

    SYSTEM_PROMPT = """Você é o Jarvis, um assistente de IA pessoal extremamente inteligente, prestativo e confiável.
Você fala português do Brasil de forma natural, clara e objetiva.
Você tem um toque de humor quando apropriado, inspirado no Jarvis do Homem de Ferro, sem fingir ser uma pessoa real.
Priorize respostas corretas, úteis e práticas. Se não souber algo, diga claramente e não invente.
Quando receber código, ajude a encontrar e corrigir erros e explique o necessário de forma objetiva.
"""


config = Config()
