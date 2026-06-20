"""Compilacao dos artefatos .pbip por gestao.

Clona o template (SemanticModel + Report) para a pasta build/, injeta o
filtro de gestao no report.json e ajusta a referencia ao SemanticModel
publicado na nuvem (schema PBIR v2.0.0).
"""

import json
import os
import shutil

import pandas as pd

from . import config


def clone_and_compile(gestao_name):
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

    # Injeta valor(es) do filtro de gestao no filterConfig do report.json
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
                # Detecta se e o painel consolidado GFP e KFW
                if gestao_name == "GFP e KFW":
                    # Busca todos os gestores KFW da planilha e inclui GFP
                    df = pd.read_excel(config.EXCEL_FILE_PATH)
                    gestores_kfw = df[df["RESPONSAVEL"].str.startswith("KFW", na=False)]["RESPONSAVEL"].unique().tolist()
                    valores_consolidado = ["GFP"] + gestores_kfw
                    values = [[{"Literal": {"Value": f"'{g}'"}}] for g in valores_consolidado]
                else:
                    # Injeta valor unico
                    values = [[{"Literal": {"Value": f"'{gestao_name}'"}}]]

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

    return new_filename, target_semantic_folder, target_report_folder


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
