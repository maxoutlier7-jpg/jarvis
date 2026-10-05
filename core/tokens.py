"""Contabilidade e orçamento de tokens das chamadas de LLM."""

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, Optional


def estimate_tokens(text: str) -> int:
    """Estimativa simples (~4 caracteres/token), arredondada para cima."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BudgetExceededError(RuntimeError):
    """Levantada quando o orçamento diário de tokens foi esgotado."""

    def __init__(self, used: int, budget: int):
        self.used = used
        self.budget = budget
        super().__init__(
            f"Orçamento diário de tokens esgotado ({used}/{budget}). "
            "Aumente TOKENS_PER_DAY no .env ou aguarde o próximo dia."
        )


class TokenTracker:
    """Soma uso real por dia/provider e mantém uma sessão em memória.

    ``daily_budget = 0`` significa ilimitado. Cada resposta bem-sucedida é
    registrada uma única vez; tentativas que falham não são contadas como uso
    confirmado, pois a API pode não fornecer os tokens consumidos.
    """

    def __init__(self, daily_budget: int, storage_path: str = ""):
        self.daily_budget = max(0, int(daily_budget))
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._days: Dict[str, Dict] = {}
        self._session = {
            "prompt": 0,
            "completion": 0,
            "total": 0,
            "cache_hits": 0,
            "requests": 0,
        }
        self._load()

    def _load(self) -> None:
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            days = data.get("days", {}) if isinstance(data, dict) else {}
            if not isinstance(days, dict):
                return
            # Ignore registros malformados em vez de impedir o Jarvis de iniciar.
            self._days = {
                str(day): value
                for day, value in days.items()
                if isinstance(value, dict)
                and all(
                    isinstance(value.get(key, 0), (int, float))
                    and value.get(key, 0) >= 0
                    for key in ("prompt", "completion", "total")
                )
            }
        except (OSError, ValueError, TypeError):
            print(f"[Aviso] Não foi possível ler {self.storage_path}; começando do zero.")

    def _save(self) -> None:
        if not self.storage_path:
            return
        directory = os.path.dirname(os.path.abspath(self.storage_path))
        try:
            os.makedirs(directory, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".usage-", suffix=".tmp", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"days": self._days}, fh, ensure_ascii=False, indent=2)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(temp_path, self.storage_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except OSError as exc:
            print(f"[Aviso] Não foi possível salvar o uso em {self.storage_path}: {exc}")

    def record(
        self, provider: str, model: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        prompt_tokens = max(0, int(prompt_tokens or 0))
        completion_tokens = max(0, int(completion_tokens or 0))
        with self._lock:
            day = self._days.setdefault(
                _today(), {"prompt": 0, "completion": 0, "total": 0, "by_provider": {}}
            )
            by_provider = day.setdefault("by_provider", {})
            stats = by_provider.setdefault(
                f"{provider}:{model}", {"prompt": 0, "completion": 0, "total": 0}
            )
            for target in (day, stats):
                target["prompt"] += prompt_tokens
                target["completion"] += completion_tokens
                target["total"] += prompt_tokens + completion_tokens
            self._session["prompt"] += prompt_tokens
            self._session["completion"] += completion_tokens
            self._session["total"] += prompt_tokens + completion_tokens
            self._session["requests"] += 1
            self._save()

    def record_cache_hit(self) -> None:
        with self._lock:
            self._session["cache_hits"] += 1

    def used_today(self) -> int:
        with self._lock:
            day = self._days.get(_today(), {})
            return int(day.get("total", 0))

    def remaining_today(self) -> Optional[int]:
        if not self.daily_budget:
            return None
        return max(0, self.daily_budget - self.used_today())

    def enforce_budget(self, extra: int = 0) -> None:
        """Bloqueia somente quando existe limite diário configurado."""
        if not self.daily_budget:
            return
        used = self.used_today()
        if used + max(0, int(extra)) > self.daily_budget:
            raise BudgetExceededError(used, self.daily_budget)

    def summary(self) -> Dict:
        with self._lock:
            session = dict(self._session)
            day = dict(self._days.get(_today(), {}))
        used_today = int(day.get("total", 0))
        return {
            **session,
            "session_prompt": session["prompt"],
            "session_completion": session["completion"],
            "session_total": session["total"],
            "today_prompt": int(day.get("prompt", 0)),
            "today_completion": int(day.get("completion", 0)),
            "today_total": used_today,
            "budget": self.daily_budget,
            "remaining": max(0, self.daily_budget - used_today) if self.daily_budget else None,
        }
