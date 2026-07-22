"""Validacao dos pre-requisitos antes de iniciar o pipeline (Etapa 0)."""

import os
import sys
from pathlib import Path

from rich.table import Table
from rich import box

from . import config
from .console import console, mask, banner


def verificar_pre_requisitos(mode):
    """Valida credenciais, templates e planilhas; aborta se algo essencial faltar.

    `mode` ("gestao" ou "lideres") decide quais planilhas de entrada sao exigidas.
    """
    banner(
        "ETAPA 0 / PRE-REQUISITOS",
        "Validacao de credenciais, templates e planilha",
        cor="bright_blue",
    )

    tabela = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    tabela.add_column("Item", style="white")
    tabela.add_column("Status", justify="center", width=10)
    tabela.add_column("Detalhe", style="dim")

    tudo_ok = True

    pares_env = [
        ("TENANT_ID", config.TENANT_ID),
        ("CLIENT_ID", config.CLIENT_ID),
        ("CLIENT_SECRET", config.CLIENT_SECRET),
        ("WORKSPACE_ID", config.WORKSPACE_ID),
        ("URL_ENCRYPTION_KEY", config.URL_ENCRYPTION_KEY),
    ]
    for var, val in pares_env:
        if val:
            tabela.add_row(f"ENV {var}", "[green]OK[/green]", mask(val))
        else:
            tabela.add_row(f"ENV {var}", "[red]FALTA[/red]", "Variavel ausente no .env")
            tudo_ok = False

    caminhos = [
        (config.BASE_SEMANTIC_MODEL, "Template SemanticModel"),
        (config.BASE_REPORT, "Template Report"),
    ]
    if mode == "gestao":
        caminhos += [
            (config.EXCEL_FILE_PATH, "Planilha de gestores"),
            (config.REFRESH_SCHEDULE_PATH, "Planilha de agendamento"),
        ]
    else:
        caminhos += [
            (config.LIDERES_PROJETO_PATH, "Planilha de lideres/doacoes"),
            (config.LIDERES_REFRESH_SCHEDULE_PATH, "Planilha de agendamento"),
        ]
    for caminho, label in caminhos:
        if os.path.exists(caminho):
            tabela.add_row(label, "[green]OK[/green]", caminho)
        else:
            tabela.add_row(label, "[red]FALTA[/red]", f"Nao encontrado: {caminho}")
            tudo_ok = False

    # O cadastro de usuarios Lovable e opcional (so para geracao SQL)
    if os.path.exists(config.USER_DASHBOARDS_PATH):
        tabela.add_row("Cadastro usuarios Lovable", "[green]OK[/green]", config.USER_DASHBOARDS_PATH)

    Path(config.BUILD_DIR).mkdir(exist_ok=True)
    Path(config.LOG_DIR).mkdir(exist_ok=True)
    Path(config.SQL_DIR).mkdir(exist_ok=True)
    tabela.add_row("Diretorio build/", "[green]OK[/green]", os.path.abspath(config.BUILD_DIR))
    tabela.add_row("Diretorio logs/", "[green]OK[/green]", os.path.abspath(config.LOG_DIR))
    tabela.add_row("Diretorio sql/", "[green]OK[/green]", os.path.abspath(config.SQL_DIR))

    console.print(tabela)

    if not tudo_ok:
        console.print("\n[red bold]Pre-requisitos nao atendidos. Abortando.[/red bold]\n")
        sys.exit(1)

    console.print("[green bold]>> Pre-requisitos validados.[/green bold]")
