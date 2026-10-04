"""Sistema simples de plugins do Jarvis."""

from typing import Callable, Dict, Optional

Plugin = Callable[..., str]
PLUGINS: Dict[str, Plugin] = {}


def register(name: str, func: Plugin) -> Plugin:
    """Registra e devolve um plugin."""
    key = name.strip().lower()
    if not key:
        raise ValueError("O nome do plugin não pode ser vazio")
    PLUGINS[key] = func
    return func


def get_plugin(name: str) -> Optional[Plugin]:
    """Obtém um plugin pelo nome."""
    return PLUGINS.get(name.strip().lower())


def list_plugins() -> list[str]:
    """Retorna os nomes dos plugins registrados."""
    return sorted(PLUGINS)
