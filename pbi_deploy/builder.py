"""Compilacao dos artefatos .pbip por gestao (RESPONSAVEL) ou por lider (DOAÇÃO).

Clona o template (SemanticModel + Report) para a pasta build/, injeta o filtro
report-level no report.json e ajusta a referencia ao SemanticModel publicado na
nuvem (schema PBIR v2.0.0). Ha duas variacoes de compilacao:

    clone_and_compile_gestao  filtro dGestão.RESPONSAVEL (com casos GFP+KFW e GRI/SG).
    clone_and_compile_lider   filtro dDoação.DOAÇÃO (uma lista de doacoes por lider).
"""

import json
import os
import shutil

import pandas as pd

from . import config


def _literal(valor):
    """Monta um literal de texto da query semantica ('valor').

    Apostrofos internos precisam ser duplicados, senao fecham o literal antes da
    hora e o Power BI rejeita a query com
    InvalidOrMalformedSemanticQueryDefinition_InvalidLiteralExpression
    (ex.: a doacao "FUNDO L'ORÉAL_2024_1").
    """
    escapado = str(valor).replace("'", "''")
    return {"Literal": {"Value": f"'{escapado}'"}}


def clone_and_compile_gestao(gestao_name):
    """Clona o template para a gestao e injeta o filtro de RESPONSAVEL no report."""
    new_filename = f"{config.PBI_PROJECT_NAME} - {gestao_name}"
    target_semantic_folder = os.path.join(config.BUILD_DIR, f"{new_filename}.SemanticModel")
    target_report_folder = os.path.join(config.BUILD_DIR, f"{new_filename}.Report")

    if os.path.exists(target_semantic_folder):
        shutil.rmtree(target_semantic_folder)
    if os.path.exists(target_report_folder):
        shutil.rmtree(target_report_folder)

    shutil.copytree(config.BASE_SEMANTIC_MODEL, target_semantic_folder)
    shutil.copytree(config.BASE_REPORT, target_report_folder)

    report_json_path = os.path.join(target_report_folder, "definition", "report.json")
    if os.path.exists(report_json_path):
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_json = json.load(f)

        filter_config = report_json.get("filterConfig", {})
        filtros = filter_config.get("filters", [])

        for filtro in filtros:
            entity = (
                filtro.get("field", {})
                .get("Column", {})
                .get("Expression", {})
                .get("SourceRef", {})
                .get("Entity")
            )
            prop = filtro.get("field", {}).get("Column", {}).get("Property")
            if entity == "dGestão" and prop == "RESPONSAVEL":
                if gestao_name == "GFP e KFW":
                    df = pd.read_excel(config.EXCEL_FILE_PATH)
                    gestores_kfw = df[df["RESPONSAVEL"].str.startswith("KFW", na=False)]["RESPONSAVEL"].unique().tolist()
                    valores_consolidado = ["GFP"] + gestores_kfw
                    values = [[_literal(g)] for g in valores_consolidado]
                elif gestao_name == "GRI":
                    df = pd.read_excel(config.EXCEL_FILE_PATH)
                    gestores_sg = df[df["SUPERINTENDÊNCIA"] == "SG"]["RESPONSAVEL"].unique().tolist()
                    values = [[_literal(g)] for g in gestores_sg]
                else:
                    values = [[_literal(gestao_name)]]

                filtro["filter"] = {
                    "Version": 2,
                    "From": [
                        {"Name": "d", "Entity": "dGestão", "Type": 0}
                    ],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "d"}},
                                                "Property": "RESPONSAVEL"
                                            }
                                        }
                                    ],
                                    "Values": values
                                }
                            }
                        }
                    ]
                }
                break

        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)

    # Para a GRI, restringe a pagina Pessoal apenas aos dados da propria GRI.
    if gestao_name == "GRI":
        _injetar_filtro_pessoal_gri(target_report_folder)

    return new_filename, target_semantic_folder, target_report_folder


def _injetar_filtro_pessoal_gri(target_report_folder):
    """Adiciona filtro page-level RESPONSAVEL='GRI' na pagina Pessoal.

    O report-level ja possui filtro com todos os responsaveis da
    superintendencia SG. Este filtro de pagina restringe a pagina Pessoal
    para exibir apenas os dados da GRI (interseccao com o filtro global).
    """
    pages_dir = os.path.join(target_report_folder, "definition", "pages")
    if not os.path.isdir(pages_dir):
        return

    for page_folder in os.listdir(pages_dir):
        page_json_path = os.path.join(pages_dir, page_folder, "page.json")
        if not os.path.isfile(page_json_path):
            continue

        with open(page_json_path, "r", encoding="utf-8") as f:
            page_data = json.load(f)

        if page_data.get("displayName") != "Pessoal":
            continue

        filtro_responsavel = {
            "name": "filtro_gri_pessoal",
            "field": {
                "Column": {
                    "Expression": {
                        "SourceRef": {"Entity": "dGestão"}
                    },
                    "Property": "RESPONSAVEL"
                }
            },
            "type": "Categorical",
            "filter": {
                "Version": 2,
                "From": [
                    {"Name": "d", "Entity": "dGestão", "Type": 0}
                ],
                "Where": [
                    {
                        "Condition": {
                            "In": {
                                "Expressions": [
                                    {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Source": "d"}},
                                            "Property": "RESPONSAVEL"
                                        }
                                    }
                                ],
                                "Values": [
                                    [{"Literal": {"Value": "'GRI'"}}]
                                ]
                            }
                        }
                    }
                ]
            },
            "howCreated": "User",
            "isLockedInViewMode": True
        }

        fc = page_data.setdefault("filterConfig", {})
        fc.setdefault("filters", []).append(filtro_responsavel)

        with open(page_json_path, "w", encoding="utf-8") as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
        break


def clone_and_compile_lider(lider_name, doacoes):
    """Clona o template para o lider e injeta o filtro de DOAÇÃO no report.

    `doacoes` e a lista de doacoes lideradas pelo lider, ja normalizadas para
    casar com a coluna dDoação.DOAÇÃO do modelo. O filtro report-level fica
    travado em modo de visualizacao (isLockedInViewMode).
    """
    new_filename = f"{config.PBI_PROJECT_NAME} - {lider_name}"
    target_semantic_folder = os.path.join(config.BUILD_DIR, f"{new_filename}.SemanticModel")
    target_report_folder = os.path.join(config.BUILD_DIR, f"{new_filename}.Report")

    if os.path.exists(target_semantic_folder):
        shutil.rmtree(target_semantic_folder)
    if os.path.exists(target_report_folder):
        shutil.rmtree(target_report_folder)

    shutil.copytree(config.BASE_SEMANTIC_MODEL, target_semantic_folder)
    shutil.copytree(config.BASE_REPORT, target_report_folder)

    report_json_path = os.path.join(target_report_folder, "definition", "report.json")
    if os.path.exists(report_json_path):
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_json = json.load(f)

        report_json["filterConfig"] = {"filters": [_montar_filtro_doacao(doacoes)]}

        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)

    return new_filename, target_semantic_folder, target_report_folder


def _montar_filtro_doacao(doacoes):
    """Monta o filtro report-level dDoação.DOAÇÃO IN (doacoes)."""
    values = [[_literal(d)] for d in doacoes]
    return {
        "name": "filtro_doacao_lider",
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": "dDoação"}},
                "Property": "DOAÇÃO",
            }
        },
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [
                {"Name": "d", "Entity": "dDoação", "Type": 0}
            ],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Source": "d"}},
                                        "Property": "DOAÇÃO",
                                    }
                                }
                            ],
                            "Values": values,
                        }
                    }
                }
            ],
        },
        "howCreated": "User",
        "isLockedInViewMode": True,
    }


def fix_report_cloud_reference(target_report_folder, cloud_dataset_id):
    """
    Injeta a referencia ao SemanticModel publicado seguindo o schema PBIR v2.0.0
    da Fabric API. O formato canonico (doc oficial Microsoft Learn) e':

        "datasetReference": {
            "byConnection": {
                "connectionString": "semanticmodelid=<dataset_id>"
            }
        }

    Nao usar 'byItemId' (nao existe no schema), nem a estrutura legacy com
    pbiModelDatabaseName/pbiModelVirtualServerName/connectionType (rejeitada
    pelo schema v2.0.0 como 'additional properties').
    """
    pbir_path = os.path.join(target_report_folder, "definition.pbir")
    if not os.path.exists(pbir_path):
        return
    with open(pbir_path, "r", encoding="utf-8") as f:
        pbir_json = json.load(f)

    pbir_json["datasetReference"] = {
        "byConnection": {
            "connectionString": f"semanticmodelid={cloud_dataset_id}"
        }
    }

    with open(pbir_path, "w", encoding="utf-8") as f:
        json.dump(pbir_json, f, ensure_ascii=False, indent=2)
