"""
Sistema de plugins do Jarvis.

Aqui você pode adicionar novas habilidades (abrir sites, clima, 
controle do computador, etc).

Exemplo de como criar um plugin no futuro:

def plugin_clima(cidade: str) -> str:
    # lógica aqui
    return f"O clima em {cidade} está..."
"""

# Lista de plugins registrados (por enquanto vazio, pronto para expansão)
PLUGINS = {}

def register(name: str, func):
    """Registra um novo plugin."""
    PLUGINS[name] = func

def get_plugin(name: str):
    return PLUGINS.get(name)
