from typing import Dict, List


class Memory:
    """Memória limitada que remove turnos completos antes de cortar mensagens."""

    def __init__(self, max_messages: int = 30):
        # Limite par para que uma conversa completa caiba sem truncar o par.
        requested = max(2, int(max_messages))
        self.max_messages = requested - (requested % 2)
        self.messages: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role deve ser 'user' ou 'assistant'")
        if not isinstance(content, str):
            raise TypeError("content deve ser texto")
        self.messages.append({"role": role, "content": content})
        self._trim()

    def add_exchange(self, user_content: str, assistant_content: str) -> None:
        """Adiciona uma troca válida de forma atômica para preservar o par."""
        if not isinstance(user_content, str) or not isinstance(assistant_content, str):
            raise TypeError("as mensagens devem ser texto")
        self.messages.extend(
            [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": assistant_content},
            ]
        )
        self._trim()

    def _trim(self) -> None:
        while len(self.messages) > self.max_messages:
            # O histórico normal é composto por pares user/assistant. Remova o
            # turno mais antigo inteiro; só remova uma mensagem em dados órfãos.
            if (
                len(self.messages) >= 2
                and self.messages[0]["role"] == "user"
                and self.messages[1]["role"] == "assistant"
            ):
                del self.messages[:2]
            else:
                del self.messages[0]
        # Não mantenha uma resposta assistant sem a pergunta correspondente.
        while self.messages and self.messages[0]["role"] != "user":
            del self.messages[0]

    def get_history(self) -> List[Dict[str, str]]:
        return [message.copy() for message in self.messages]

    def clear(self) -> None:
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)
