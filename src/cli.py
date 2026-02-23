import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live

from agent import MCPAgent
from config import get_anthropic_key, get_database_url

console = Console()

BANNER = """
[bold blue]╔══════════════════════════════════════════╗
║     AGENTE DE CONSULTA MULTIPLATAFORMA   ║
║         PostgreSQL + Google Sheets       ║
╚══════════════════════════════════════════╝[/bold blue]
"""

HELP_TEXT = """[bold]Comandos disponibles:[/bold]
  [cyan]/salir[/cyan]  o  [cyan]/exit[/cyan]   → Termina la sesión
  [cyan]/limpiar[/cyan]               → Limpia la pantalla
  [cyan]/ayuda[/cyan]                 → Muestra este mensaje

[bold]Ejemplos de consultas:[/bold]
  • "Listá todas las tablas disponibles"
  • "Mostrá los primeros 10 registros de la tabla clientes"
  • "¿Cuántos pedidos hubo en enero de 2024?"
  • "Resumí las ventas por categoría"
  • "Actualizá el email del cliente con id 5 a nuevo@email.com"
"""


def validate_environment():
    """Verifica que las variables de entorno necesarias estén configuradas."""
    errors = []
    try:
        get_anthropic_key()
    except ValueError as e:
        errors.append(str(e))
    try:
        get_database_url()
    except ValueError as e:
        errors.append(str(e))

    if errors:
        console.print("\n[bold red]Error de configuración:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        console.print(
            "\n[yellow]Copiá [bold].env.example[/bold] como [bold].env[/bold] "
            "y completá los valores requeridos.[/yellow]\n"
        )
        sys.exit(1)


def _display_tool_call(tool_name: str, tool_input: dict, result: str):
    """Muestra en pantalla la herramienta que ejecutó el agente y su resultado."""
    import json

    # Formatear el input como SQL o JSON según corresponda
    sql = tool_input.get("query") or tool_input.get("sql") or tool_input.get("statement")
    if sql:
        body = f"[bold yellow]SQL:[/bold yellow]\n{sql.strip()}"
    else:
        body = f"[bold yellow]Input:[/bold yellow]\n{json.dumps(tool_input, indent=2, ensure_ascii=False)}"

    # Primeras líneas del resultado para no saturar la pantalla
    result_preview = result.strip()
    if len(result_preview) > 400:
        result_preview = result_preview[:400] + "\n[dim]... (truncado)[/dim]"

    console.print(
        Panel(
            f"{body}\n\n[bold yellow]Resultado:[/bold yellow]\n{result_preview}",
            title=f"[bold yellow]⚙ Herramienta: {tool_name}[/bold yellow]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


async def process_query(agent: MCPAgent, user_input: str):
    """Procesa una consulta del usuario mostrando un spinner mientras espera."""
    tool_calls = []

    def on_tool_call(name, input_, result):
        # Guardamos para mostrar después de que el spinner termina
        tool_calls.append((name, input_, result))

    with Live(
        Spinner("dots", text="[cyan]El agente está procesando tu consulta...[/cyan]"),
        console=console,
        refresh_per_second=10,
    ):
        response = await agent.run_query(user_input, on_tool_call=on_tool_call)

    # Mostrar las herramientas que se ejecutaron
    for name, input_, result in tool_calls:
        _display_tool_call(name, input_, result)

    console.print(
        Panel(
            response,
            title="[bold green]Respuesta del Agente[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


async def main():
    console.print(BANNER)
    validate_environment()

    console.print(
        Panel(
            HELP_TEXT,
            title="[bold]Bienvenido[/bold]",
            border_style="blue",
            padding=(0, 2),
        )
    )

    # Conectar al servidor MCP una sola vez al inicio
    agent = MCPAgent()
    with Live(
        Spinner("dots", text="[cyan]Conectando a PostgreSQL vía MCP...[/cyan]"),
        console=console,
        refresh_per_second=10,
    ):
        try:
            await agent.connect()
        except Exception as e:
            console.print(f"\n[bold red]Error al conectar con MCP:[/bold red] {e}\n")
            sys.exit(1)

    console.print(
        "[dim]Conexión establecida con PostgreSQL vía MCP. "
        "Escribí tu consulta para comenzar.[/dim]\n"
    )

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]Consulta[/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Sesión finalizada.[/yellow]")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/salir", "/exit", "salir", "exit"):
                console.print("\n[yellow]¡Hasta luego![/yellow]")
                break

            if user_input.lower() in ("/limpiar", "/clear"):
                console.clear()
                console.print(BANNER)
                agent.clear_history()
                continue

            if user_input.lower() in ("/ayuda", "/help"):
                console.print(Panel(HELP_TEXT, border_style="blue", padding=(0, 2)))
                continue

            try:
                await process_query(agent, user_input)
            except Exception as e:
                console.print(f"\n[bold red]Error:[/bold red] {e}\n")

            console.print()
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
