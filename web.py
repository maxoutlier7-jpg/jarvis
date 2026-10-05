"""Interface web do Jarvis (Gradio) com painel de controle de tokens."""

import inspect

import gradio as gr

from core.config import config
from core.llm import LLM, ProviderError
from core.memory import Memory
from core.tokens import BudgetExceededError

llm = LLM()
memory = Memory(config.MEMORY_MAX_MESSAGES)


def _fmt(number: int) -> str:
    return f"{number:,}".replace(",", ".")


def _usage_markdown() -> str:
    summary = llm.tracker.summary()
    used_today, budget = summary["today_total"], summary["budget"]
    lines = [
        "### Controle de tokens",
        f"**Sessão:** {_fmt(summary['session_total'])} tokens ({_fmt(summary['session_prompt'])} entrada / {_fmt(summary['session_completion'])} saída)",
        f"**Requisições:** {summary['requests']} · **Cache:** {summary['cache_hits']} respostas reaproveitadas",
    ]
    if budget:
        pct = min(100.0, used_today / budget * 100.0)
        filled = int(pct // 5)
        lines.append(f"**Hoje:** {_fmt(used_today)} / {_fmt(budget)} tokens ({pct:.1f}%) — restam **{_fmt(summary['remaining'])}**")
        lines.append("`" + "▓" * filled + "░" * (20 - filled) + "`")
    else:
        lines.append(f"**Hoje:** {_fmt(used_today)} tokens · sem limite diário")
    return "\n\n".join(lines)


def respond(message: str, chat_history: list, provider: str):
    message = (message or "").strip()
    history = list(chat_history or [])
    if provider and provider.strip().lower() != llm.provider:
        if not llm.set_provider(provider):
            history.append({"role": "assistant", "content": f"Provedor '{provider}' não disponível; provedor mantido: {llm.provider}."})
            return "", history, _usage_markdown()
    if not message:
        return "", history, _usage_markdown()
    try:
        result = llm.chat(message, memory.get_history())
        memory.add_exchange(message, result.text)
        if result.cached:
            footer = "\n\n---\n*Resposta reutilizada do cache — 0 tokens*"
        else:
            footer = f"\n\n---\n*{_fmt(result.prompt_tokens)} entrada / {_fmt(result.completion_tokens)} saída · modelo: {result.model}*"
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": result.text + footer},
        ])
    except BudgetExceededError as exc:
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"Limite de uso: {exc}"},
        ])
    except ProviderError as exc:
        label = "Gemini" if exc.provider == "gemini" else "Groq" if exc.provider == "groq" else exc.provider
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"Falha no provedor {label}: {exc.cause}"},
        ])
    except Exception as exc:  # noqa: BLE001
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"Erro inesperado: {exc}"},
        ])
    return "", history, _usage_markdown()


def clear_chat():
    memory.clear()
    return [], _usage_markdown()


def clear_cache():
    llm.cache.clear()
    return _usage_markdown()


def build_app() -> gr.Blocks:
    providers = llm.available_providers()
    with gr.Blocks(title="Jarvis") as app:
        gr.Markdown("# Jarvis\nAssistente de IA com **controle de tokens** e sem fallback automático entre provedores.")
        with gr.Row():
            with gr.Column(scale=3):
                chatbot_options = {"label": "Conversa", "height": 420}
                # Gradio 4 aceita type="messages"; Gradio 6 removeu o argumento
                # e passou a usar esse formato como padrão.
                if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
                    chatbot_options["type"] = "messages"
                chatbot = gr.Chatbot(**chatbot_options)
                with gr.Row():
                    message = gr.Textbox(placeholder="Fale com o Jarvis...", label="Mensagem", autofocus=True, scale=4)
                    send_btn = gr.Button("Enviar", variant="primary", scale=1)
                with gr.Row():
                    clear_btn = gr.Button("Limpar conversa")
                    cache_btn = gr.Button("Limpar cache")
            with gr.Column(scale=2):
                provider_dd = gr.Dropdown(choices=providers, value=llm.provider if llm.provider in providers else None, label="Provedor (sem fallback cruzado)", interactive=True)
                usage_md = gr.Markdown(_usage_markdown())
        inputs, outputs = [message, chatbot, provider_dd], [message, chatbot, usage_md]
        send_btn.click(respond, inputs, outputs)
        message.submit(respond, inputs, outputs)
        clear_btn.click(clear_chat, None, [chatbot, usage_md])
        cache_btn.click(clear_cache, None, [usage_md])
    return app


if __name__ == "__main__":
    build_app().launch()
