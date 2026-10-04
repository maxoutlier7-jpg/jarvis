from typing import List, Dict
from core.config import config

class LLM:
    """Camada unificada para Gemini e Groq."""
    
    def __init__(self):
        self.provider = config.DEFAULT_PROVIDER
        self._gemini_model = None
        self._groq_client = None
        self._setup()
    
    def _setup(self):
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.GEMINI_API_KEY)
                self._gemini_model = genai.GenerativeModel(
                    model_name=config.GEMINI_MODEL,
                    system_instruction=config.SYSTEM_PROMPT
                )
            except Exception as e:
                print(f"[Aviso] Não foi possível inicializar Gemini: {e}")
        
        if config.GROQ_API_KEY:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=config.GROQ_API_KEY)
            except Exception as e:
                print(f"[Aviso] Não foi possível inicializar Groq: {e}")
    
    def set_provider(self, provider: str) -> bool:
        provider = provider.lower().strip()
        if provider == "gemini" and self._gemini_model:
            self.provider = "gemini"
            return True
        if provider == "groq" and self._groq_client:
            self.provider = "groq"
            return True
        return False
    
    def available_providers(self) -> List[str]:
        providers = []
        if self._gemini_model:
            providers.append("gemini")
        if self._groq_client:
            providers.append("groq")
        return providers
    
    def chat(self, user_message: str, history: List[Dict[str, str]]) -> str:
        if self.provider == "gemini" and self._gemini_model:
            return self._chat_gemini(user_message, history)
        elif self.provider == "groq" and self._groq_client:
            return self._chat_groq(user_message, history)
        else:
            # Fallback automático
            if self._gemini_model:
                self.provider = "gemini"
                return self._chat_gemini(user_message, history)
            if self._groq_client:
                self.provider = "groq"
                return self._chat_groq(user_message, history)
            return "Erro: Nenhuma API configurada. Coloque GEMINI_API_KEY ou GROQ_API_KEY no arquivo .env"
    
    def _chat_gemini(self, user_message: str, history: List[Dict[str, str]]) -> str:
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})
        
        chat = self._gemini_model.start_chat(history=gemini_history)
        response = chat.send_message(user_message)
        return response.text
    
    def _chat_groq(self, user_message: str, history: List[Dict[str, str]]) -> str:
        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        messages.append({"role": "user", "content": user_message})
        
        completion = self._groq_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return completion.choices[0].message.content
