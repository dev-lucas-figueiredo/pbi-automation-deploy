"""Descoberta do template e nomes publicados (Mudanca 1)."""

import json

import pytest

from src import builder, config


def _criar_par(base, nome_modelo, nome_relatorio=None):
    nome_relatorio = nome_relatorio or nome_modelo
    modelo = base / f"{nome_modelo}.SemanticModel"
    relatorio = base / f"{nome_relatorio}.Report"
    for pasta, tipo in ((modelo, "SemanticModel"), (relatorio, "Report")):
        pasta.mkdir(parents=True)
        (pasta / ".platform").write_text(
            json.dumps({"metadata": {"type": tipo, "displayName": "Original"}}), encoding="utf-8"
        )
    (relatorio / "definition.pbir").write_text(
        json.dumps({"datasetReference": {"byPath": {"path": f"../{nome_modelo}.SemanticModel"}}}),
        encoding="utf-8",
    )
    return modelo, relatorio


def test_descoberta_zero_pares(tmp_path):
    modelo, relatorio, erro = config.descobrir_template(tmp_path)
    assert modelo is None and relatorio is None
    assert "nenhuma" in erro


def test_descoberta_um_par_com_qualquer_nome(tmp_path):
    _criar_par(tmp_path, "Painel Financeiro Executivo - 2.0")
    modelo, relatorio, erro = config.descobrir_template(tmp_path)
    assert erro is None
    assert modelo.endswith("Painel Financeiro Executivo - 2.0.SemanticModel")
    assert relatorio.endswith("Painel Financeiro Executivo - 2.0.Report")


def test_descoberta_dois_pares(tmp_path):
    _criar_par(tmp_path, "A")
    _criar_par(tmp_path, "B")
    modelo, relatorio, erro = config.descobrir_template(tmp_path)
    assert modelo is None and relatorio is None
    assert "A.SemanticModel" in erro and "B.SemanticModel" in erro


def test_descoberta_nomes_base_diferentes(tmp_path):
    _criar_par(tmp_path, "A", "B")
    _, _, erro = config.descobrir_template(tmp_path)
    assert "nao coincidem" in erro


def test_descoberta_pasta_inexistente_nao_levanta(tmp_path):
    _, _, erro = config.descobrir_template(tmp_path / "nao_existe")
    assert erro


@pytest.fixture
def template_configurado(tmp_path, monkeypatch):
    template = tmp_path / "template"
    template.mkdir()
    modelo, relatorio = _criar_par(template, "Nome Qualquer do Arquivo")
    (relatorio / "definition").mkdir()
    (relatorio / "definition" / "report.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "BASE_SEMANTIC_MODEL", str(modelo))
    monkeypatch.setattr(config, "BASE_REPORT", str(relatorio))
    monkeypatch.setattr(config, "TEMPLATE_ERRO", None)
    monkeypatch.setattr(config, "BUILD_DIR", str(tmp_path / "build"))
    monkeypatch.setattr(config, "PBI_PUBLISHED_NAME", "Painel Teste")
    (tmp_path / "build").mkdir()
    return tmp_path


def test_nome_publicado_gestao(template_configurado):
    nome, pasta_modelo, pasta_report = builder.clone_and_compile_gestao("DAF")
    assert nome == "Painel Teste - DAF"
    assert pasta_modelo.endswith("Painel Teste - DAF.SemanticModel")
    assert pasta_report.endswith("Painel Teste - DAF.Report")
    for pasta in (pasta_modelo, pasta_report):
        platform = json.loads(open(f"{pasta}/.platform", encoding="utf-8").read())
        assert platform["metadata"]["displayName"] == "Painel Teste - DAF"


def test_nome_publicado_lider(template_configurado):
    nome, _, pasta_report = builder.clone_and_compile_lider("Fabiana Cunha", ["DOACAO X"])
    assert nome == "Painel Teste - Fabiana Cunha"
    builder.fix_report_cloud_reference(pasta_report, "abc-123")
    pbir = json.loads(open(f"{pasta_report}/definition.pbir", encoding="utf-8").read())
    assert pbir["datasetReference"] == {"byConnection": {"connectionString": "semanticmodelid=abc-123"}}


def test_clone_sem_template_levanta_erro_claro(monkeypatch):
    monkeypatch.setattr(config, "BASE_SEMANTIC_MODEL", None)
    monkeypatch.setattr(config, "BASE_REPORT", None)
    monkeypatch.setattr(config, "TEMPLATE_ERRO", "sem template")
    with pytest.raises(ValueError, match="sem template"):
        builder.clone_and_compile_lider("X", ["Y"])
