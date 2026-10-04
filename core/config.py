import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gemini").lower().strip()
    
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    
    SYSTEM_PROMPT = """Você é o Jarvis, um assistente de IA pessoal extremamente inteligente, prestativo e com personalidade.
Você fala português do Brasil de forma natural e clara.
Você é direto, útil e tem um toque de humor quando apropriado (como o Jarvis do Homem de Ferro).
Sempre tente ser o mais útil possível. Se não souber algo, admita e ofereça alternativas.
"""

config = Config()
