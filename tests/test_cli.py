from core.cache import ResponseCache
from core.tokens import TokenTracker


def test_terminal_provider_and_operational_commands_work_with_mocks(monkeypatch, capsys):
    import main as cli

    class FakeLLM:
        def __init__(self):
            self.provider = "gemini"
            self._available = ["gemini", "groq"]
            self.tracker = TokenTracker(0, "")
            self.cache = ResponseCache(0, 0)

        def available_providers(self):
            return list(self._available)

        def set_provider(self, provider):
            if provider not in self._available:
                return False
            self.provider = provider
            return True

    fake = FakeLLM()
    commands = iter([
        "/help", "/status", "/usage", "/provider groq", "/provider gemini",
        "/clear", "/cache", "/quit",
    ])
    monkeypatch.setattr(cli, "LLM", lambda: fake)
    monkeypatch.setattr(cli.console, "input", lambda _prompt: next(commands))
    cli.main()
    output = capsys.readouterr().out
    assert fake.provider == "gemini"
    assert "SYSTEM STATUS" in output
    assert "Provedor atual" in output
    assert "Provedor alterado para" in output
    assert "Memória limpa" in output
    assert "Cache de respostas limpo" in output
