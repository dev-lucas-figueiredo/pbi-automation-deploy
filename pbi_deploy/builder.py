"""Compilacao dos artefatos .pbip por lider de projeto.

Clona o template (SemanticModel + Report) para a pasta build/, injeta o
filtro com as doacoes do lider no report.json e ajusta a referencia ao
SemanticModel publicado na nuvem (schema PBIR v2.0.0).
"""

import json
import os
import shutil

from . import config


def clone_and_compile(lider_name, doacoes):
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
    values = [[{"Literal": {"Value": f"'{d}'"}}] for d in doacoes]
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
