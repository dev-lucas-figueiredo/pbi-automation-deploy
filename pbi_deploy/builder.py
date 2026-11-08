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


def _clonar_template(nome_publicado):
    """Copia o template para build/ com o nome publicado e ajusta o .platform.

    O Report do template referencia o modelo por byPath com o nome do arquivo
    original; isso e substituido por byConnection em fix_report_cloud_reference
    (Fase 2), entao o nome da pasta de destino pode ser o nome publicado.
    """
    if not (config.BASE_SEMANTIC_MODEL and config.BASE_REPORT):
        raise ValueError(config.TEMPLATE_ERRO or "Template nao encontrado")

    target_semantic_folder = os.path.join(config.BUILD_DIR, f"{nome_publicado}.SemanticModel")
    target_report_folder = os.path.join(config.BUILD_DIR, f"{nome_publicado}.Report")

    for pasta in (target_semantic_folder, target_report_folder):
        if os.path.exists(pasta):
            shutil.rmtree(pasta)

    shutil.copytree(config.BASE_SEMANTIC_MODEL, target_semantic_folder)
    shutil.copytree(config.BASE_REPORT, target_report_folder)

    for pasta in (target_semantic_folder, target_report_folder):
        _ajustar_display_name(pasta, nome_publicado)

    return target_semantic_folder, target_report_folder


def _ajustar_display_name(pasta_item, nome_publicado):
    """Troca metadata.displayName do .platform pelo nome publicado do item."""
    platform_path = os.path.join(pasta_item, ".platform")
    if not os.path.isfile(platform_path):
        return
    with open(platform_path, "r", encoding="utf-8") as f:
        platform = json.load(f)
    platform.setdefault("metadata", {})["displayName"] = nome_publicado
    with open(platform_path, "w", encoding="utf-8") as f:
        json.dump(platform, f, ensure_ascii=False, indent=2)


def clone_and_compile_gestao(gestao_name):
    """Clona o template para a gestao e injeta o filtro de RESPONSAVEL no report."""
    new_filename = f"{config.PBI_PUBLISHED_NAME} - {gestao_name}"
    target_semantic_folder, target_report_folder = _clonar_template(new_filename)

    report_json_path = os.path.join(target_report_folder, "definition", "report.json")
    if os.path.exists(report_json_path):
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_json = json.load(f)

        responsaveis = _responsaveis_da_gestao(gestao_name)
        # Sem valores o filtro nao restringe nada: melhor falhar do que publicar
        # um painel de gestao mostrando os dados de todas as gestoes.
        if not responsaveis:
            raise ValueError(f"Nenhum RESPONSAVEL encontrado para a gestao '{gestao_name}'")
        report_json["filterConfig"] = {"filters": [_montar_filtro_responsavel(responsaveis)]}

        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)

    # Para a GRI, restringe a pagina Pessoal apenas aos dados da propria GRI.
    if gestao_name == "GRI":
        _injetar_filtro_pessoal_gri(target_report_folder)

    return new_filename, target_semantic_folder, target_report_folder


def _responsaveis_da_gestao(gestao_name):
    """Devolve a lista de RESPONSAVEL que entram no painel daquela gestao.

    Casos especiais: "GFP e KFW" agrupa GFP com todas as gestoes KFW; a GRI
    recebe todos os responsaveis da superintendencia SG. As demais gestoes
    filtram apenas o proprio nome.
    """
    if gestao_name == "GFP e KFW":
        df = pd.read_excel(config.EXCEL_FILE_PATH)
        gestores_kfw = df[df["RESPONSAVEL"].str.startswith("KFW", na=False)]["RESPONSAVEL"].unique().tolist()
        return ["GFP"] + gestores_kfw
    if gestao_name == "GRI":
        df = pd.read_excel(config.EXCEL_FILE_PATH)
        return df[df["SUPERINTENDÊNCIA"] == "SG"]["RESPONSAVEL"].dropna().unique().tolist()
    return [gestao_name]


def _montar_filtro_responsavel(responsaveis):
    """Monta o filtro report-level dGestão.RESPONSAVEL IN (responsaveis)."""
    values = [[_literal(r)] for r in responsaveis]
    return {
        "name": "filtro_responsavel_gestao",
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": "dGestão"}},
                "Property": "RESPONSAVEL",
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
                                        "Property": "RESPONSAVEL",
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
    new_filename = f"{config.PBI_PUBLISHED_NAME} - {lider_name}"
    target_semantic_folder, target_report_folder = _clonar_template(new_filename)

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
