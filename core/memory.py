from typing import List, Dict

class Memory:
    """Memória simples da conversa atual."""
    
    def __init__(self, max_messages: int = 30):
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages
    
    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        # Mantém só as últimas mensagens para não estourar o contexto
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_history(self) -> List[Dict[str, str]]:
        return self.messages.copy()
    
    def clear(self):
        self.messages.clear()
    
    def __len__(self):
        return len(self.messages)
