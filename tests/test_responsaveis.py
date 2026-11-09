"""Regras de RESPONSAVEL por gestao (Mudanca 2: GRI e gestao comum)."""

import pandas as pd
import pytest

from pbi_deploy import builder, config, pipeline


@pytest.fixture
def planilha(tmp_path, monkeypatch):
    df = pd.DataFrame(
        {
            "RESPONSAVEL": ["GFP", "KFW1", "KFW2", "DAF", "GRI", "PDI", "SG"],
            "SUPERINTENDÊNCIA": ["SF", "SF", "SF", "SF", "SG", "SG", "SG"],
        }
    )
    caminho = tmp_path / "dados_entrada.xlsx"
    with pd.ExcelWriter(caminho) as writer:
        df.to_excel(writer, sheet_name=config.SHEET_GESTAO_AREAS, index=False)
    monkeypatch.setattr(config, "EXCEL_INPUT_PATH", str(caminho))
    monkeypatch.setattr(config, "EXCEL_FILE_PATH", str(caminho))
    return df


def test_gfp_e_kfw(planilha):
    assert builder._responsaveis_da_gestao("GFP e KFW") == ["GFP", "KFW1", "KFW2"]


def test_gestao_comum(planilha):
    assert builder._responsaveis_da_gestao("DAF") == ["DAF"]


def test_gri_e_gestao_comum(planilha):
    assert builder._responsaveis_da_gestao("GRI") == ["GRI"]


def test_gri_nao_gera_filtro_de_pagina():
    assert not hasattr(builder, "_injetar_filtro_pessoal_gri")


def test_identificar_gestores_trata_gri_como_comum(planilha):
    gestores, kfw, invalidos = pipeline._identificar_gestores(planilha)
    assert "GRI" in gestores and "PDI" in gestores
    assert "SG" not in gestores and invalidos == ["SG"]
    assert "GFP e KFW" in gestores and "GFP" not in gestores
