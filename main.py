#!/usr/bin/env python3
"""
Jarvis - Assistente de IA pessoal super inteligente
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from core.llm import LLM
from core.memory import Memory

console = Console()

def print_banner():
    banner = Text()
    banner.append("\n  ╔══════════════════════════════════════╗\n", style="bold cyan")
    banner.append("  ║           J A R V I S                 ║\n", style="bold cyan")
    banner.append("  ║     Assistente Super Inteligente      ║\n", style="bold cyan")
    banner.append("  ╚══════════════════════════════════════╝\n", style="bold cyan")
    console.print(banner)

def print_help():
    help_text = """
**Comandos disponíveis:**

- Digite normalmente → conversa com o Jarvis
- `/clear` → limpa a memória da conversa
- `/provider gemini` → usa Google Gemini
- `/provider groq` → usa Groq (mais rápido)
- `/status` → mostra status atual
- `/help` → mostra esta ajuda
- `/exit` ou `/quit` → sai do programa
"""
    console.print(Markdown(help_text))

def main():
    print_banner()
    
    llm = LLM()
    memory = Memory()
    
    available = llm.available_providers()
    
    if not available:
        console.print("[bold red]Nenhuma API configurada![/bold red]")
        console.print("Abra o arquivo [cyan].env[/cyan] e coloque pelo menos uma chave:")
        console.print("  • GEMINI_API_KEY  → https://aistudio.google.com/apikey")
        console.print("  • GROQ_API_KEY    → https://console.groq.com/keys")
        console.print("\nDepois rode novamente: [green]python main.py[/green]")
        return
    
    console.print(f"[green]✓[/green] Provedores disponíveis: [cyan]{', '.join(available)}[/cyan]")
    console.print(f"[green]✓[/green] Usando: [bold cyan]{llm.provider}[/bold cyan]")
    console.print("[dim]Digite /help para ver os comandos\n[/dim]")
    
    while True:
        try:
            user_input = console.input("[bold green]Você > [/bold green]").strip()
            
            if not user_input:
                continue
            
            # Comandos
            if user_input.lower() in ("/exit", "/quit", "sair", "exit"):
                console.print("[cyan]Até mais, senhor.[/cyan]")
                break
            
            if user_input.lower() in ("/help", "ajuda"):
                print_help()
                continue
            
            if user_input.lower() == "/clear":
                memory.clear()
                console.print("[yellow]Memória limpa.[/yellow]")
                continue
            
            if user_input.lower().startswith("/provider"):
                parts = user_input.split()
                if len(parts) < 2:
                    console.print("[red]Uso: /provider gemini  ou  /provider groq[/red]")
                    continue
                new_provider = parts[1].lower()
                if llm.set_provider(new_provider):
                    console.print(f"[green]Provedor alterado para:[/green] [cyan]{new_provider}[/cyan]")
                else:
                    console.print(f"[red]Provedor '{new_provider}' não disponível.[/red]")
                    console.print(f"Disponíveis: {', '.join(llm.available_providers())}")
                continue
            
            if user_input.lower() == "/status":
                console.print(f"Provedor atual: [cyan]{llm.provider}[/cyan]")
                console.print(f"Mensagens na memória: [cyan]{len(memory)}[/cyan]")
                console.print(f"Provedores disponíveis: [cyan]{', '.join(available)}[/cyan]")
                continue
            
            # Conversa normal
            with console.status("[bold cyan]Jarvis pensando...[/bold cyan]", spinner="dots"):
                response = llm.chat(user_input, memory.get_history())
            
            # Salva na memória
            memory.add("user", user_input)
            memory.add("assistant", response)
            
            # Mostra resposta
            console.print()
            console.print(Panel(
                Markdown(response),
                title="[bold cyan]Jarvis[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            ))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[cyan]Até mais, senhor.[/cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Erro:[/bold red] {e}")

if __name__ == "__main__":
    main()
