from typing import Dict, List


class Memory:
    """Memória simples e limitada da conversa atual."""

    def __init__(self, max_messages: int = 30):
        self.max_messages = max(2, max_messages)
        self.messages: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role deve ser 'user' ou 'assistant'")

        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_history(self) -> List[Dict[str, str]]:
        return [message.copy() for message in self.messages]

    def clear(self) -> None:
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)
