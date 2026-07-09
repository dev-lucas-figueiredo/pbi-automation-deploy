"""Orquestracao do pipeline de publicacao Power BI / Fabric.

Encadeia as fases na ordem:
    Etapa 0  Pre-requisitos.
    Etapa 1  Autenticacao Azure AD.
    Etapa 2  Inspecao do workspace.
    Fase 1   Deploy dos modelos semanticos.
    Fase 2   Deploy dos relatorios vinculados.
    Fase 3   Pos-deploy (TakeOver, agendamento e refresh inicial).
    Final    Resumo executivo, log estruturado e geracao de SQL.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from . import config
from .console import console, mask, banner
from .auth import autenticar_azure
from .fabric import listar_itens_workspace, upload_item_to_fabric
from .powerbi import takeover_dataset, configurar_refresh_schedule, disparar_refresh
from .builder import clone_and_compile, fix_report_cloud_reference
from .datasources import carregar_schedule, gerar_sql_user_dashboards
from .prerequisites import verificar_pre_requisitos
from .runner import executar_fase


def _identificar_gestores(df):
    """Extrai a lista de gestores validos da planilha e monta o consolidado KFW.

    Retorna (gestores, gestores_kfw, gestores_invalidos).
    """
    # Remove gestores onde RESPONSAVEL == SUPERINTENDÊNCIA
    mask_invalidos = df["RESPONSAVEL"].fillna("") == df["SUPERINTENDÊNCIA"].fillna("")
    gestores_invalidos = df[mask_invalidos]["RESPONSAVEL"].dropna().unique().tolist()
    df_validos = df[~mask_invalidos]

    gestores = df_validos["RESPONSAVEL"].dropna().unique().tolist()

    # Identifica gestoes KFW, inclui GFP no consolidado e remove GFP da lista individual
    gestores_kfw = [g for g in gestores if str(g).startswith("KFW")]
    if gestores_kfw:
        gestores = [g for g in gestores if g != "GFP"]
        gestores.append("GFP e KFW")

    return gestores, gestores_kfw, gestores_invalidos


def main():
    inicio = datetime.now()

    console.print(
        Panel(
            Text.assemble(
                ("PIPELINE DE PUBLICACAO POWER BI\n", "bold white"),
                (f"Projeto:   {config.PBI_PROJECT_NAME}\n", "white"),
                (f"Workspace: {mask(config.WORKSPACE_ID)}\n", "dim"),
                (f"Iniciado:  {inicio.strftime('%Y-%m-%d %H:%M:%S')}", "dim"),
            ),
            border_style="bold bright_green",
            padding=(1, 4),
        )
    )

    verificar_pre_requisitos()
    token = autenticar_azure()
    items_na_nuvem = listar_itens_workspace(token)

    df = pd.read_excel(config.EXCEL_FILE_PATH)
    gestores, gestores_kfw, gestores_invalidos = _identificar_gestores(df)

    if gestores_invalidos:
        console.print(
            f"[dim]Ignorados por RESPONSAVEL == SUPERINTENDÊNCIA: {', '.join(gestores_invalidos)}[/dim]\n"
        )

    console.print(f"\n[bold cyan]Gestores identificados na planilha:[/bold cyan] {len(gestores) - (1 if gestores_kfw else 0)}")
    if gestores_kfw:
        console.print(f"[bold cyan]Painel consolidado GFP e KFW adicionado[/bold cyan] (agrupa GFP + {len(gestores_kfw)} gestões KFW)")
    if "GRI" in gestores:
        gestores_sg = df[df["SUPERINTENDÊNCIA"] == "SG"]["RESPONSAVEL"].unique().tolist()
        console.print(
            f"[bold cyan]Painel GRI ampliado:[/bold cyan] inclui todos os responsaveis da superintendencia SG "
            f"({', '.join(gestores_sg)}) | pagina Pessoal restrita a GRI"
        )

    memoria_deploy = {}

    # --- FASE 1: modelos semanticos ---
    def processar_modelo(gestor):
        nome_final, pasta_model, pasta_report = clone_and_compile(gestor)
        status, dataset_id = upload_item_to_fabric(
            token, nome_final, "SemanticModel", pasta_model, items_na_nuvem
        )
        memoria_deploy[gestor] = {
            "nome_final": nome_final,
            "pasta_report": pasta_report,
            "dataset_id": dataset_id,
        }
        return status, f"dataset_id={mask(dataset_id) if dataset_id else 'N/A'}"

    log_fase1 = executar_fase(
        "FASE 1 / MODELOS SEMANTICOS",
        f"Compilacao e deploy de {len(gestores)} modelos",
        gestores,
        processar_modelo,
        cor="bright_magenta",
    )

    # Re-fetch para a Fase 2 capturar IDs novos
    console.print(
        "\n[dim]Aguardando 3s para propagacao de itens recem-criados...[/dim]"
    )
    time.sleep(3)
    items_atualizados = listar_itens_workspace(
        token, titulo="ETAPA 3 / RE-SINCRONIZACAO WORKSPACE"
    )

    # --- FASE 2: relatorios vinculados ---
    def processar_relatorio(gestor):
        dados = memoria_deploy[gestor]
        fix_report_cloud_reference(dados["pasta_report"], dados["dataset_id"])
        status, item_id = upload_item_to_fabric(
            token, dados["nome_final"], "Report", dados["pasta_report"], items_atualizados
        )
        return status, f"report_id={mask(item_id) if item_id else 'LRO'}"

    gestores_fase2 = list(memoria_deploy.keys())
    log_fase2 = executar_fase(
        "FASE 2 / RELATORIOS VINCULADOS",
        f"Deploy de {len(gestores_fase2)} relatorios",
        gestores_fase2,
        processar_relatorio,
        cor="bright_magenta",
    )

    # --- FASE 3: pos-deploy (TakeOver + schedule + refresh inicial) ---
    banner(
        "FASE 3 / POS-DEPLOY",
        "TakeOver, credenciais SharePoint, agendamento e refresh inicial",
        cor="bright_magenta",
    )

    schedule_map = carregar_schedule()
    console.print(f"  Agendamentos carregados de [cyan]refresh_schedule.xlsx[/cyan]: {len(schedule_map)} gestores\n")

    def processar_pos_deploy(gestor):
        dataset_id = memoria_deploy[gestor]["dataset_id"]
        if not dataset_id:
            raise Exception("dataset_id ausente")

        horarios = schedule_map.get(gestor, ["08:00", "18:00"])

        takeover_dataset(token, dataset_id)
        configurar_refresh_schedule(token, dataset_id, horarios)
        disparar_refresh(token, dataset_id)

        schedule_str = ",".join(horarios) if horarios else "desativado"
        return "Configurado", f"schedule={schedule_str} | refresh enfileirado"

    gestores_fase3 = list(memoria_deploy.keys())
    log_fase3 = executar_fase(
        "FASE 3 / POS-DEPLOY",
        f"Configurando {len(gestores_fase3)} modelos",
        gestores_fase3,
        processar_pos_deploy,
        cor="bright_magenta",
    )
    s3 = sum(1 for r in log_fase3 if r["ok"])
    f3 = len(log_fase3) - s3

    console.print(
        "[dim]Refresh enfileirado. Os dados sao carregados em background "
        "e podem levar alguns minutos. Para alterar horarios, edite data/refresh_schedule.xlsx "
        "e rode o script novamente.[/dim]"
    )

    # --- SUMARIO ---
    fim = datetime.now()
    duracao = (fim - inicio).total_seconds()

    s1 = sum(1 for r in log_fase1 if r["ok"])
    f1 = len(log_fase1) - s1
    s2 = sum(1 for r in log_fase2 if r["ok"])
    f2 = len(log_fase2) - s2

    sumario = Table(
        title="\nRESUMO EXECUTIVO",
        title_style="bold magenta",
        show_header=True,
        header_style="bold magenta",
        box=box.HEAVY_EDGE,
    )
    sumario.add_column("Fase", style="white")
    sumario.add_column("Total", justify="right")
    sumario.add_column("Sucesso", justify="right", style="green")
    sumario.add_column("Falha", justify="right", style="red")
    sumario.add_column("Taxa", justify="right")

    def taxa(s, t):
        return f"{(s / t * 100):.1f}%" if t > 0 else "-"

    sumario.add_row(
        "Fase 1 - Modelos Semanticos", str(s1 + f1), str(s1), str(f1), taxa(s1, s1 + f1)
    )
    sumario.add_row(
        "Fase 2 - Relatorios", str(s2 + f2), str(s2), str(f2), taxa(s2, s2 + f2)
    )
    sumario.add_row(
        "Fase 3 - Refresh", str(s3 + f3), str(s3), str(f3), taxa(s3, s3 + f3)
    )
    console.print(sumario)

    cor_final = "green" if (f1 + f2 + f3) == 0 else ("yellow" if (s1 + s2 + s3) > 0 else "red")
    console.print(
        Panel(
            Text.assemble(
                (f"Duracao total:  {duracao:.1f}s\n", "white"),
                (f"Finalizado em:  {fim.strftime('%Y-%m-%d %H:%M:%S')}\n", "dim"),
                (
                    f"Status global:  "
                    f"{'SUCESSO' if (f1 + f2 + f3) == 0 else 'PARCIAL' if (s1 + s2 + s3) > 0 else 'FALHA'}",
                    f"bold {cor_final}",
                ),
            ),
            border_style=cor_final,
            padding=(1, 2),
        )
    )

    # Persistir log estruturado
    log_path = Path(config.LOG_DIR) / f"deploy_{inicio.strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "inicio": inicio.isoformat(),
                "fim": fim.isoformat(),
                "duracao_s": round(duracao, 2),
                "workspace_id_mask": mask(config.WORKSPACE_ID),
                "fase1": log_fase1,
                "fase2": log_fase2,
                "fase3": log_fase3,
                "totais": {
                    "fase1_ok": s1,
                    "fase1_erro": f1,
                    "fase2_ok": s2,
                    "fase2_erro": f2,
                    "fase3_ok": s3,
                    "fase3_erro": f3,
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    console.print(f"\n[dim]Log estruturado salvo em: {log_path}[/dim]\n")

    # Gerar SQL de carga de user_dashboards se planilha existir
    if os.path.exists(config.USER_DASHBOARDS_PATH):
        try:
            gerar_sql_user_dashboards()
        except Exception as e:
            console.print(f"[yellow]Falha ao gerar SQL de user_dashboards: {e}[/yellow]\n")

    sys.exit(0 if (f1 + f2 + f3) == 0 else 1)


def run():
    """Wrapper com tratamento de erros e codigos de saida usado pelo entrypoint."""
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrompido pelo usuario.[/yellow]\n")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red bold]Erro fatal nao tratado: {type(e).__name__}: {e}[/red bold]")
        console.print(traceback.format_exc(), style="red dim")
        sys.exit(2)
