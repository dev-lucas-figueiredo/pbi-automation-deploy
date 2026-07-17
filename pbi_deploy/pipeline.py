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
from .datasources import carregar_lideres_doacoes, carregar_schedule, gerar_sql_user_dashboards
from .prerequisites import verificar_pre_requisitos
from .runner import executar_fase


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

    lideres = carregar_lideres_doacoes()
    lideres_lista = list(lideres.keys())
    total_doacoes = sum(len(v) for v in lideres.values())

    console.print(
        f"\n[bold cyan]Lideres identificados na planilha:[/bold cyan] {len(lideres_lista)} "
        f"([dim]{total_doacoes} doacoes mapeadas[/dim])"
    )

    memoria_deploy = {}

    def processar_modelo(lider):
        nome_final, pasta_model, pasta_report = clone_and_compile(lider, lideres[lider])
        status, dataset_id = upload_item_to_fabric(
            token, nome_final, "SemanticModel", pasta_model, items_na_nuvem
        )
        memoria_deploy[lider] = {
            "nome_final": nome_final,
            "pasta_report": pasta_report,
            "dataset_id": dataset_id,
        }
        return status, f"dataset_id={mask(dataset_id) if dataset_id else 'N/A'}"

    log_fase1 = executar_fase(
        "FASE 1 / MODELOS SEMANTICOS",
        f"Compilacao e deploy de {len(lideres_lista)} modelos",
        lideres_lista,
        processar_modelo,
        cor="bright_magenta",
    )

    console.print(
        "\n[dim]Aguardando 3s para propagacao de itens recem-criados...[/dim]"
    )
    time.sleep(3)
    items_atualizados = listar_itens_workspace(
        token, titulo="ETAPA 3 / RE-SINCRONIZACAO WORKSPACE"
    )

    def processar_relatorio(lider):
        dados = memoria_deploy[lider]
        fix_report_cloud_reference(dados["pasta_report"], dados["dataset_id"])
        status, item_id = upload_item_to_fabric(
            token, dados["nome_final"], "Report", dados["pasta_report"], items_atualizados
        )
        return status, f"report_id={mask(item_id) if item_id else 'LRO'}"

    lideres_fase2 = list(memoria_deploy.keys())
    log_fase2 = executar_fase(
        "FASE 2 / RELATORIOS VINCULADOS",
        f"Deploy de {len(lideres_fase2)} relatorios",
        lideres_fase2,
        processar_relatorio,
        cor="bright_magenta",
    )

    banner(
        "FASE 3 / POS-DEPLOY",
        "TakeOver, credenciais SharePoint, agendamento e refresh inicial",
        cor="bright_magenta",
    )

    schedule_map = carregar_schedule()
    console.print(f"  Agendamentos carregados de [cyan]refresh_schedule.xlsx[/cyan]: {len(schedule_map)} lideres\n")

    def processar_pos_deploy(lider):
        dataset_id = memoria_deploy[lider]["dataset_id"]
        if not dataset_id:
            raise Exception("dataset_id ausente")

        horarios = schedule_map.get(lider, ["08:00", "18:00"])

        takeover_dataset(token, dataset_id)
        configurar_refresh_schedule(token, dataset_id, horarios)
        disparar_refresh(token, dataset_id)

        schedule_str = ",".join(horarios) if horarios else "desativado"
        return "Configurado", f"schedule={schedule_str} | refresh enfileirado"

    lideres_fase3 = list(memoria_deploy.keys())
    log_fase3 = executar_fase(
        "FASE 3 / POS-DEPLOY",
        f"Configurando {len(lideres_fase3)} modelos",
        lideres_fase3,
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
