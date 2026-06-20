"""Executor generico de uma fase do pipeline.

Recebe a lista de gestores e uma funcao `processar_um(gestor)` que retorna
(status, detalhe) ou levanta excecao. Cuida de barra de progresso, tabela de
resultados, contagem de sucessos/falhas e do log estruturado por gestor.
"""

import time

from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich import box

from .console import console, banner
from .errors import APIError


def executar_fase(titulo_fase, subtitulo, gestores, processar_um, cor="green"):
    """Roda `processar_um` para cada gestor e retorna a lista de resultados."""
    banner(titulo_fase, subtitulo, cor=cor)

    resultados = []
    sucessos, falhas = 0, 0

    tabela = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    tabela.add_column("#", style="dim", justify="right", width=4)
    tabela.add_column("Gestao", width=14, style="white")
    tabela.add_column("Status", justify="center", width=10)
    tabela.add_column("Acao", width=14, style="cyan")
    tabela.add_column("Tempo", justify="right", width=8, style="dim")
    tabela.add_column("Detalhe", overflow="fold")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(titulo_fase, total=len(gestores))

        for idx, gestor in enumerate(gestores, 1):
            progress.update(task, description=f"Processando [{gestor}]")
            t0 = time.time()
            try:
                status, detalhe = processar_um(gestor)
                elapsed = time.time() - t0
                tabela.add_row(
                    str(idx),
                    gestor,
                    "[green]OK[/green]",
                    status,
                    f"{elapsed:.1f}s",
                    detalhe,
                )
                resultados.append(
                    {
                        "gestor": gestor,
                        "ok": True,
                        "status": status,
                        "tempo_s": round(elapsed, 2),
                        "detalhe": detalhe,
                    }
                )
                sucessos += 1
            except APIError as e:
                elapsed = time.time() - t0
                tabela.add_row(
                    str(idx),
                    gestor,
                    "[red]ERRO[/red]",
                    e.action,
                    f"{elapsed:.1f}s",
                    str(e),
                )
                resultados.append(
                    {
                        "gestor": gestor,
                        "ok": False,
                        "status": "ERRO",
                        "tempo_s": round(elapsed, 2),
                        "detalhe": str(e),
                        "status_code": e.status_code,
                        "headers": e.headers,
                    }
                )
                falhas += 1
            except Exception as e:
                elapsed = time.time() - t0
                detalhe = f"{type(e).__name__}: {str(e)[:300]}"
                tabela.add_row(
                    str(idx),
                    gestor,
                    "[red]ERRO[/red]",
                    "interno",
                    f"{elapsed:.1f}s",
                    detalhe,
                )
                resultados.append(
                    {
                        "gestor": gestor,
                        "ok": False,
                        "status": "ERRO",
                        "tempo_s": round(elapsed, 2),
                        "detalhe": detalhe,
                    }
                )
                falhas += 1
            finally:
                progress.advance(task)

    console.print(tabela)
    cor_taxa = "green" if falhas == 0 else ("yellow" if sucessos > 0 else "red")
    console.print(
        f"  [bold]Resultado:[/bold] [green]{sucessos} OK[/green]  "
        f"[red]{falhas} ERRO[/red]  "
        f"taxa de sucesso: [{cor_taxa}]"
        f"{(sucessos / max(len(gestores), 1) * 100):.1f}%[/{cor_taxa}]"
    )
    return resultados
