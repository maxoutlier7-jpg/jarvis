#!/usr/bin/env python3
"""Jarvis - Assistente de IA pessoal."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from core.config import config
from core.llm import LLM
from core.memory import Memory

console = Console()


def print_banner() -> None:
    banner = Text()
    banner.append("\n  ╔══════════════════════════════════════╗\n", style="bold cyan")
    banner.append("  ║              J A R V I S             ║\n", style="bold cyan")
    banner.append("  ║       Assistente de IA pessoal       ║\n", style="bold cyan")
    banner.append("  ╚══════════════════════════════════════╝\n", style="bold cyan")
    console.print(banner)


def print_help() -> None:
    help_text = """
**Comandos disponíveis:**

- Digite normalmente → conversa com o Jarvis
- `/clear` → limpa a memória da conversa
- `/provider gemini` → usa Google Gemini
- `/provider groq` → usa Groq
- `/status` → mostra o status atual
- `/help` → mostra esta ajuda
- `/exit` ou `/quit` → encerra o programa
"""
    console.print(Markdown(help_text))


def main() -> None:
    print_banner()

    llm = LLM()
    memory = Memory(config.MEMORY_MAX_MESSAGES)
    available = llm.available_providers()

    if not available:
        console.print("[bold red]Nenhuma API configurada.[/bold red]")
        console.print("Crie um arquivo [cyan].env[/cyan] baseado no [cyan].env.example[/cyan].")
        console.print("Configure pelo menos uma destas chaves:")
        console.print("  • GEMINI_API_KEY")
        console.print("  • GROQ_API_KEY")
        console.print("\nDepois rode novamente: [green]python main.py[/green]")
        return

    console.print(
        f"[green]✓[/green] Provedores disponíveis: "
        f"[cyan]{', '.join(available)}[/cyan]"
    )
    console.print(f"[green]✓[/green] Usando: [bold cyan]{llm.provider}[/bold cyan]")
    console.print("[dim]Digite /help para ver os comandos.\n[/dim]")

    while True:
        try:
            user_input = console.input("[bold green]Você > [/bold green]").strip()
            if not user_input:
                continue

            command = user_input.lower()

            if command in {"/exit", "/quit", "exit", "sair"}:
                console.print("[cyan]Até mais, senhor.[/cyan]")
                break

            if command in {"/help", "ajuda"}:
                print_help()
                continue

            if command == "/clear":
                memory.clear()
                console.print("[yellow]Memória limpa.[/yellow]")
                continue

            if command.startswith("/provider"):
                parts = command.split(maxsplit=1)
                if len(parts) != 2:
                    console.print("[red]Uso: /provider gemini ou /provider groq[/red]")
                    continue

                provider = parts[1].strip()
                if llm.set_provider(provider):
                    console.print(
                        f"[green]Provedor alterado para:[/green] [cyan]{provider}[/cyan]"
                    )
                else:
                    console.print(f"[red]Provedor '{provider}' não disponível.[/red]")
                    console.print(
                        f"Disponíveis: {', '.join(llm.available_providers()) or 'nenhum'}"
                    )
                continue

            if command == "/status":
                console.print(f"Provedor atual: [cyan]{llm.provider}[/cyan]")
                console.print(f"Mensagens na memória: [cyan]{len(memory)}[/cyan]")
                console.print(
                    "Provedores disponíveis: "
                    f"[cyan]{', '.join(llm.available_providers())}[/cyan]"
                )
                continue

            history = memory.get_history()
            with console.status("[bold cyan]Jarvis pensando...[/bold cyan]", spinner="dots"):
                response = llm.chat(user_input, history)

            memory.add("user", user_input)
            memory.add("assistant", response)

            console.print()
            console.print(
                Panel(
                    Markdown(response),
                    title="[bold cyan]Jarvis[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
            console.print()

        except KeyboardInterrupt:
            console.print("\n[cyan]Até mais, senhor.[/cyan]")
            break
        except EOFError:
            console.print("\n[cyan]Até mais, senhor.[/cyan]")
            break
        except Exception as exc:
            console.print(f"[bold red]Erro inesperado:[/bold red] {exc}")


if __name__ == "__main__":
    main()
