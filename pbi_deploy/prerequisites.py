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

    if config.REFRESH_NOTIFY_OPTION in config.NOTIFY_OPTIONS_VALIDAS:
        tabela.add_row("ENV REFRESH_NOTIFY_OPTION", "[green]OK[/green]", config.REFRESH_NOTIFY_OPTION)
    else:
        tabela.add_row(
            "ENV REFRESH_NOTIFY_OPTION",
            "[red]INVALIDO[/red]",
            f"'{config.REFRESH_NOTIFY_OPTION}' (aceitos: {', '.join(config.NOTIFY_OPTIONS_VALIDAS)})",
        )
        tudo_ok = False

    if config.TEMPLATE_ERRO:
        tabela.add_row("Template (.pbip)", "[red]FALTA[/red]", config.TEMPLATE_ERRO)
        tudo_ok = False
    else:
        arquivos_template = [
            (config.BASE_SEMANTIC_MODEL, "Template SemanticModel", None),
            (config.BASE_REPORT, "Template Report", None),
            (config.BASE_SEMANTIC_MODEL, "SemanticModel/.platform", ".platform"),
            (config.BASE_REPORT, "Report/.platform", ".platform"),
            (config.BASE_REPORT, "Report/definition.pbir", "definition.pbir"),
        ]
        for pasta, label, arquivo in arquivos_template:
            caminho = os.path.join(pasta, arquivo) if arquivo else pasta
            if os.path.exists(caminho):
                tabela.add_row(label, "[green]OK[/green]", caminho)
            else:
                tabela.add_row(label, "[red]FALTA[/red]", f"Nao encontrado: {caminho}")
                tudo_ok = False

    tabela.add_row("Nome publicado", "[green]OK[/green]", config.PBI_PUBLISHED_NAME)

    if not os.path.exists(config.EXCEL_INPUT_PATH):
        tabela.add_row("Planilha de entrada", "[red]FALTA[/red]", f"Nao encontrada: {config.EXCEL_INPUT_PATH}")
        tudo_ok = False
    else:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(config.EXCEL_INPUT_PATH, read_only=True)
            abas = wb.sheetnames
            wb.close()

            if mode == "gestao":
                necessarias = [
                    (config.SHEET_GESTAO_AREAS, "Aba de gestores"),
                    (config.SHEET_GESTAO_SCHEDULE, "Aba de agendamento"),
                ]
            else:
                necessarias = [
                    (config.SHEET_LIDERES_DOACOES, "Aba de lideres/doacoes"),
                    (config.SHEET_LIDERES_SCHEDULE, "Aba de agendamento"),
                ]

            for aba_nome, rotulo in necessarias:
                if aba_nome in abas:
                    tabela.add_row(rotulo, "[green]OK[/green]", f"{config.EXCEL_INPUT_PATH} -> [{aba_nome}]")
                else:
                    tabela.add_row(rotulo, "[red]FALTA[/red]", f"Aba '{aba_nome}' ausente em {config.EXCEL_INPUT_PATH}")
                    tudo_ok = False

            aba_usr = config.USER_DASHBOARDS_ABAS.get(mode)
            if aba_usr in abas:
                tabela.add_row("Aba usuarios Lovable", "[green]OK[/green]", f"{config.EXCEL_INPUT_PATH} -> [{aba_usr}]")
            else:
                tabela.add_row("Aba usuarios Lovable", "[yellow]OPCIONAL[/yellow]", f"Aba '{aba_usr}' ausente (geracao SQL sera pulada)")
        except Exception as e:
            tabela.add_row("Planilha de entrada", "[red]ERRO[/red]", f"Falha ao ler {config.EXCEL_INPUT_PATH}: {e}")
            tudo_ok = False

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
