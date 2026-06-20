"""Saida visual no terminal via rich: console compartilhado e helpers.

Reune o console singleton e os utilitarios de apresentacao reutilizados pelas
fases (mascaramento de segredos e banners). Importe sempre `console` daqui
para garantir uma unica instancia em todo o pipeline.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def mask(value, keep=4):
    """Mascara um valor sensivel, mostrando apenas inicio e fim."""
    if not value:
        return "[vazio]"
    if len(str(value)) <= keep * 2:
        return "***"
    return f"{value[:keep]}...{value[-keep:]}"


def banner(titulo, subtitulo=None, cor="cyan"):
    """Imprime um painel de titulo (com subtitulo opcional) destacando a etapa."""
    txt = Text(titulo, style="bold white")
    if subtitulo:
        txt.append(f"\n{subtitulo}", style="dim white")
    console.print()
    console.print(Panel(txt, border_style=cor, padding=(0, 2)))
