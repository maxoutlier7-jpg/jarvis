#!/usr/bin/env python3
"""Jarvis — Terminal de IA pessoal (estilo HUD)."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from core.config import config
from core.llm import LLM, ProviderError
from core.memory import Memory
from core.tokens import BudgetExceededError
from plugins import list_plugins

console = Console()
TAGLINE = "[dim cyan]CONTROL TODAY.  AUTOMATE TOMORROW.  LIVE BETTER.[/dim cyan]"
ONLINE = "[bold green]◆ ONLINE   [/bold green]"
READY = "[yellow]◆ READY    [/yellow]"
OK = "[bold green]◆ 100%     [/bold green]"


def boot_banner(llm: "LLM") -> None:
    art = Text()
    art.append("\n")
    art.append(
        "       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗\n"
        "       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝\n"
        "       ██║███████║██████╔╝██║   ██║██║███████╗\n"
        "  ██   ██║██╔══██╗██╔══██╗╚██╗ ██╔╝██║╚════██║\n"
        "  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║\n"
        "   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝\n",
        style="bold cyan",
    )
    art.append("       YOUR PERSONAL AI ASSISTANT\n", style="bold cyan")
    console.print(art)
    summary = llm.tracker.summary()
    if summary["budget"]:
        budget_text = (
            f"[cyan]{summary['today_total']:,}[/cyan] de [cyan]{summary['budget']:,}[/cyan] hoje "
            f"([green]{summary['remaining']:,}[/green] restantes)"
        )
    else:
        budget_text = f"[cyan]{summary['today_total']:,}[/cyan] hoje · sem limite"
    body = Text()
    for label, value in [
        ("SYSTEM STATUS    ", ONLINE),
        ("VOICE RECOGNITION ", READY),
        ("PROCESSING        ", OK),
        ("TOKEN BUDGET      ", budget_text),
    ]:
        body.append(label, style="bold cyan")
        body.append(value + "\n")
    console.print(Panel(body, title="[bold cyan]J.A.R.V.I.S. CORE · BOOT SEQUENCE[/bold cyan]", border_style="cyan", padding=(1, 2)))
    providers = ", ".join(llm.available_providers()) or "—"
    console.print(
        f"  Provedores ativos: [bold cyan]{providers}[/bold cyan]\n"
        f"  Provedor atual  : [bold cyan]{llm.provider}[/bold cyan]\n"
        f"  Modelo atual    : [bold cyan]{current_model(llm)}[/bold cyan]\n"
    )
    console.print(TAGLINE)
    console.print("\n[bold cyan]Às suas ordens, senhor. [/bold cyan]Digite [green]/help[/green] para ver o que posso fazer.\n")


def current_model(llm: "LLM") -> str:
    return config.GEMINI_MODEL if llm.provider == "gemini" else config.GROQ_MODEL


def status_brief(llm: "LLM") -> str:
    s = llm.tracker.summary()
    parts = [f"sessão: {s['session_total']:,} tok", f"cache: {s['cache_hits']} hits", f"req: {s['requests']}"]
    if s["budget"]:
        parts.append(f"orçamento: {s['today_total']:,}/{s['budget']:,}")
    return " · ".join(f"[dim cyan]{p}[/dim cyan]" for p in parts)


def help_panel() -> None:
    body = """\
**COMO O JARVIS FUNCIONA**

O modelo usa exclusivamente o provedor selecionado. O fallback, quando aplicável,
é somente entre modelos do mesmo provedor: nunca há troca automática Gemini ↔ Groq.
Erros de autenticação e quota diária não geram tentativas/fallbacks inúteis.

**O QUE O JARVIS PODE FAZER**

- Conversar em pt-BR com memória curta por pares user/assistant
- Trocar de provedor: `/provider gemini` · `/provider groq`
- Consultar uso: `/usage` · `/status`; limpar memória: `/clear`; cache: `/cache`
- Usar ferramentas controladas: calculadora segura e pesquisa web (DDGS)
- Tratar resultados web como dados não confiáveis, nunca como instruções
- Encerrar: `/exit` · `/quit` · `Ctrl+C`

**Comandos:** `/help`, `/status`, `/clear`, `/cache`, `/usage`, `/provider gemini`, `/provider groq`, `/exit`, `/quit`.
"""
    console.print(Panel(Markdown(body), title="[bold cyan]WHAT CAN JARVIS DO?[/bold cyan]", border_style="cyan", padding=(1, 2)))


def usage_panel(llm: "LLM") -> None:
    summary = llm.tracker.summary()
    lines = [
        f"Sessão: [cyan]{summary['session_total']:,}[/cyan] tokens ([cyan]{summary['session_prompt']:,}[/cyan] entrada / [cyan]{summary['session_completion']:,}[/cyan] saída)",
        f"Requisições: [cyan]{summary['requests']}[/cyan] | Cache reaproveitado: [cyan]{summary['cache_hits']}[/cyan]",
    ]
    if summary["budget"]:
        used, budget = summary["today_total"], summary["budget"]
        pct = used / budget * 100 if budget else 0
        filled = int(min(100, pct) // 5)
        lines.append(f"Hoje: [cyan]{used:,}[/cyan]/[cyan]{budget:,}[/cyan] ([yellow]{pct:.1f}%[/yellow]) — restam [green]{summary['remaining']:,}[/green]")
        lines.append("`" + "▓" * filled + "░" * (20 - filled) + "`")
    else:
        lines.append(f"Hoje: [cyan]{summary['today_total']:,}[/cyan] tokens · sem limite")
    console.print(Panel("\n".join(lines), title="[bold cyan]CONTROLE DE TOKENS[/bold cyan]", border_style="cyan", padding=(1, 2)))


def status_panel(llm: "LLM", memory: "Memory") -> None:
    providers = ", ".join(llm.available_providers()) or "nenhum"
    model = current_model(llm)
    body = (
        f"Provedor atual       : [cyan]{llm.provider}[/cyan]\n"
        f"Modelo atual         : [cyan]{model}[/cyan]\n"
        f"Provedores disponíveis: [cyan]{providers}[/cyan]\n"
        f"Mensagens na memória : [cyan]{len(memory)}[/cyan]\n"
        f"Ferramentas          : [cyan]{', '.join(list_plugins()) or 'nenhuma'}[/cyan]"
    )
    console.print(Panel(body, title="[bold cyan]SYSTEM STATUS[/bold cyan]", border_style="cyan", padding=(1, 2)))
    usage_panel(llm)


def module_panel(title: str, content: str) -> None:
    console.print(Panel(Markdown(content), title=f"[bold cyan]{title}[/bold cyan]", border_style="cyan", padding=(1, 2)))


def main() -> None:
    llm = LLM()
    memory = Memory(config.MEMORY_MAX_MESSAGES)
    if not llm.available_providers():
        console.print("[bold red]Nenhuma API configurada.[/bold red] Veja [.env.example] e configure GEMINI_API_KEY ou GROQ_API_KEY no .env.")
        return
    boot_banner(llm)
    while True:
        try:
            user_input = console.input("[bold green]Você > [/bold green]").strip()
            if not user_input:
                continue
            command = user_input.lower()
            if command in {"/exit", "/quit", "exit", "sair"}:
                console.print("[cyan]Até mais, senhor.[/cyan]")
                console.print(TAGLINE)
                break
            if command in {"/help", "ajuda"}:
                help_panel()
                continue
            if command == "/clear":
                memory.clear()
                console.print("[yellow]Memória limpa.[/yellow]")
                continue
            if command == "/cache":
                llm.cache.clear()
                console.print("[yellow]Cache de respostas limpo.[/yellow]")
                continue
            if command == "/usage":
                usage_panel(llm)
                continue
            if command == "/status":
                status_panel(llm, memory)
                continue
            if command.startswith("/provider"):
                parts = command.split(maxsplit=1)
                if len(parts) != 2:
                    console.print("[red]Uso: /provider gemini  ou  /provider groq[/red]")
                    continue
                provider = parts[1].strip()
                if llm.set_provider(provider):
                    console.print(f"[green]Provedor alterado para:[/green] [cyan]{provider}[/cyan]")
                else:
                    console.print(f"[red]Provedor '{provider}' não disponível.[/red]")
                    console.print(f"Disponíveis: {', '.join(llm.available_providers()) or 'nenhum'}")
                continue

            history = memory.get_history()
            with console.status("[bold cyan]Jarvis pensando...[/bold cyan]", spinner="dots"):
                result = llm.chat(user_input, history)
            memory.add_exchange(user_input, result.text)
            module_panel("PREPARING ◀ THINKING ◀ RESPONDING · JARVIS", result.text)
            if result.cached:
                console.print("[dim cyan]↳ resposta reutilizada do cache — 0 tokens[/dim cyan]")
            else:
                console.print(f"[dim cyan]↳ {result.prompt_tokens:,} entrada · {result.completion_tokens:,} saída · modelo: {result.model} · {status_brief(llm)}[/dim cyan]")
        except BudgetExceededError as exc:
            console.print(f"[bold red]Limite de uso:[/bold red] {exc}")
        except ProviderError as exc:
            label = "Gemini" if exc.provider == "gemini" else "Groq" if exc.provider == "groq" else exc.provider
            console.print(f"[bold red]Falha no provedor {label}:[/bold red] {exc.cause}")
            console.print(f"[dim]O provedor continua '{llm.provider}'. Use /provider para trocar manualmente.[/dim]")
        except KeyboardInterrupt:
            console.print("\n[cyan]Até mais, senhor.[/cyan]")
            console.print(TAGLINE)
            break
        except EOFError:
            console.print("\n[cyan]Até mais, senhor.[/cyan]")
            console.print(TAGLINE)
            break
        except Exception as exc:
            console.print(f"[bold red]Erro inesperado:[/bold red] {exc}")


if __name__ == "__main__":
    main()
