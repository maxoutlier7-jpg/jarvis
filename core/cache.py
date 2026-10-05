"""Cache de respostas isolado por provider/modelo, contexto e TTL."""

import hashlib
import json
import threading
import time
from typing import Dict, List, Optional, Tuple


class ResponseCache:
    """Cache FIFO em memória com TTL e limite de entradas."""

    def __init__(self, ttl_seconds: float = 86400.0, max_entries: int = 256):
        self.ttl_seconds = max(0.0, ttl_seconds)
        self.max_entries = max(0, max_entries)
        self._store: Dict[str, Tuple[float, str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def make_key(
        provider: str,
        model: str,
        user_message: str,
        history: List[Dict[str, str]],
        system_prompt: str = "",
    ) -> str:
        payload = json.dumps(
            {
                "provider": provider.strip().lower(),
                "model": model,
                "message": user_message,
                "history": [
                    {"role": m.get("role", ""), "content": m.get("content", "")}
                    for m in history
                ],
                "system_prompt": system_prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _purge_expired(self, now: float) -> None:
        expired = [
            key for key, (created_at, _) in self._store.items()
            if now - created_at >= self.ttl_seconds
        ]
        for key in expired:
            self._store.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        if self.max_entries <= 0 or self.ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            created_at, value = entry
            if now - created_at >= self.ttl_seconds:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str) -> None:
        if self.max_entries <= 0 or self.ttl_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            self._purge_expired(now)
            # Replacing an entry does not consume another slot.
            self._store.pop(key, None)
            while len(self._store) >= self.max_entries:
                self._store.pop(next(iter(self._store)))
            self._store[key] = (now, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired(time.monotonic())
            return len(self._store)
