"""Politica de notifyOption e fallback do agendamento (Mudanca 3), com HTTP simulado."""

import importlib

import pytest

from pbi_deploy import config, powerbi
from pbi_deploy.errors import APIError


class RespostaFalsa:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        self.headers = {}


@pytest.fixture
def chamadas(monkeypatch):
    """Registra os PATCH; o status por token e definido em `registro["regras"]`."""
    registro = {"calls": [], "regras": {}}

    def patch_falso(url, headers=None, json=None, timeout=None):
        token = headers["Authorization"].removeprefix("Bearer ")
        registro["calls"].append((token, json["value"]["notifyOption"]))
        return RespostaFalsa(registro["regras"].get(token, 200))

    monkeypatch.setattr(powerbi.requests, "patch", patch_falso)
    monkeypatch.setattr(config, "WORKSPACE_ID", "ws")
    return registro


def test_mail_on_failure_com_sucesso_no_delegado(chamadas):
    notify, aviso = powerbi.configurar_agendamento_com_fallback(
        "spn", "ds", ["08:00"], "MailOnFailure", lambda: "delegado"
    )
    assert (notify, aviso) == ("MailOnFailure", None)
    assert chamadas["calls"] == [("delegado", "MailOnFailure")]


@pytest.mark.parametrize("status", [401, 403])
def test_fallback_quando_delegado_recebe_erro_http(chamadas, status):
    chamadas["regras"]["delegado"] = status
    notify, aviso = powerbi.configurar_agendamento_com_fallback(
        "spn", "ds", ["08:00"], "MailOnFailure", lambda: "delegado"
    )
    assert notify == "NoNotification"
    assert str(status) in aviso
    assert chamadas["calls"] == [("delegado", "MailOnFailure"), ("spn", "NoNotification")]


def test_fallback_quando_token_delegado_falha(chamadas):
    def sem_token():
        raise Exception("Falha ao obter token delegado")

    notify, aviso = powerbi.configurar_agendamento_com_fallback(
        "spn", "ds", ["08:00"], "MailOnFailure", sem_token
    )
    assert notify == "NoNotification" and "token delegado" in aviso
    assert chamadas["calls"] == [("spn", "NoNotification")]


def test_fallback_sem_provedor_de_token(chamadas):
    notify, aviso = powerbi.configurar_agendamento_com_fallback("spn", "ds", None, "MailOnFailure")
    assert notify == "NoNotification" and aviso


def test_no_notification_usa_so_o_spn(chamadas):
    notify, aviso = powerbi.configurar_agendamento_com_fallback(
        "spn", "ds", ["08:00"], "NoNotification", lambda: pytest.fail("nao deveria pedir token")
    )
    assert (notify, aviso) == ("NoNotification", None)
    assert chamadas["calls"] == [("spn", "NoNotification")]


def test_fallback_que_tambem_falha_propaga_erro(chamadas):
    chamadas["regras"].update({"delegado": 403, "spn": 500})
    with pytest.raises(APIError):
        powerbi.configurar_agendamento_com_fallback(
            "spn", "ds", ["08:00"], "MailOnFailure", lambda: "delegado"
        )


def test_payload_leva_o_notify_option(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        powerbi.requests,
        "patch",
        lambda url, headers=None, json=None, timeout=None: enviados.append(json) or RespostaFalsa(200),
    )
    powerbi.configurar_refresh_schedule("t", "ds", ["08:00"], "MailOnFailure")
    assert enviados[0]["value"]["notifyOption"] == "MailOnFailure"
    assert enviados[0]["value"]["enabled"] is True


def test_disparar_refresh_continua_com_no_notification(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        powerbi.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None: enviados.append(json) or RespostaFalsa(202),
    )
    powerbi.disparar_refresh("t", "ds")
    assert enviados == [{"notifyOption": "NoNotification"}]


@pytest.mark.parametrize(
    "bruto,esperado",
    [("mailonfailure", "MailOnFailure"), (" NoNotification ", "NoNotification"), ("Outro", "Outro")],
)
def test_config_normaliza_notify_option(monkeypatch, bruto, esperado):
    monkeypatch.setenv("REFRESH_NOTIFY_OPTION", bruto)
    try:
        assert importlib.reload(config).REFRESH_NOTIFY_OPTION == esperado
    finally:
        monkeypatch.undo()
        importlib.reload(config)
