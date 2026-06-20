"""Operacoes da Power BI REST API sobre datasets publicados.

Cobre os endpoints `https://api.powerbi.com/v1.0/myorg/...`: tomada de
posse (TakeOver), configuracao de credenciais SharePoint, agendamento de
refresh e disparo de refresh imediato.
"""

import json

import requests

from . import config
from .errors import APIError


def takeover_dataset(pbi_token, dataset_id):
    """Reassume ownership do SemanticModel em nome do SPN."""
    url = f"{config.PBI_API_BASE}/groups/{config.WORKSPACE_ID}/datasets/{dataset_id}/Default.TakeOver"
    r = requests.post(
        url, headers={"Authorization": f"Bearer {pbi_token}"}, timeout=30
    )
    if r.status_code not in [200, 202]:
        raise APIError("TakeOver", r.status_code, r.text, dict(r.headers), url)


def configurar_credenciais_sharepoint(delegated_token, dataset_id):
    """
    Configura credenciais SharePoint via OAuth2 com token delegado da conta
    de servico (consultor.pg@fas-amazonia.org). Token delegado e necessario
    porque a API de gateway do Power BI exige contexto de usuario para
    configurar datasources de nuvem como SharePoint.
    """
    url_ds = f"{config.PBI_API_BASE}/groups/{config.WORKSPACE_ID}/datasets/{dataset_id}/datasources"
    r = requests.get(
        url_ds, headers={"Authorization": f"Bearer {delegated_token}"}, timeout=30
    )
    if r.status_code != 200:
        raise APIError("GetDatasources", r.status_code, r.text, dict(r.headers), url_ds)

    datasources = r.json().get("value", [])
    if not datasources:
        raise Exception("Nenhum datasource encontrado no modelo.")

    credentials_payload = json.dumps({
        "credentialData": [{"name": "accessToken", "value": delegated_token}]
    })
    headers = {
        "Authorization": f"Bearer {delegated_token}",
        "Content-Type": "application/json",
    }
    for ds in datasources:
        gateway_id = ds.get("gatewayId")
        datasource_id = ds.get("datasourceId")
        if not gateway_id or not datasource_id:
            continue
        url_cred = f"{config.PBI_API_BASE}/gateways/{gateway_id}/datasources/{datasource_id}"
        rc = requests.patch(
            url_cred,
            headers=headers,
            json={
                "credentialDetails": {
                    "credentialType": "OAuth2",
                    "credentials": credentials_payload,
                    "encryptedConnection": "Encrypted",
                    "encryptionAlgorithm": "None",
                    "privacyLevel": "Organizational",
                }
            },
            timeout=30,
        )
        if rc.status_code not in [200, 204]:
            raise APIError("SetCredentials", rc.status_code, rc.text, dict(rc.headers), url_cred)


def configurar_refresh_schedule(pbi_token, dataset_id, horarios=None):
    """
    Configura refresh agendado com os horarios fornecidos (fuso Manaus, UTC-4).
    Se horarios for lista vazia, desativa o agendamento automatico.
    Se horarios for None, usa o padrao 08:00 e 18:00.
    """
    if horarios is None:
        horarios = ["08:00", "18:00"]

    url = f"{config.PBI_API_BASE}/groups/{config.WORKSPACE_ID}/datasets/{dataset_id}/refreshSchedule"
    payload = {
        "value": {
            "enabled": bool(horarios),
            "days": [
                "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday", "Saturday",
            ],
            "times": horarios if horarios else ["08:00"],
            "localTimeZoneId": "SA Western Standard Time",
            "notifyOption": "NoNotification",
        }
    }
    r = requests.patch(
        url,
        headers={"Authorization": f"Bearer {pbi_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if r.status_code not in [200, 204]:
        raise APIError("RefreshSchedule", r.status_code, r.text, dict(r.headers), url)


def disparar_refresh(pbi_token, dataset_id):
    """Dispara refresh imediato assincrono."""
    url = f"{config.PBI_API_BASE}/groups/{config.WORKSPACE_ID}/datasets/{dataset_id}/refreshes"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {pbi_token}", "Content-Type": "application/json"},
        json={"notifyOption": "NoNotification"},
        timeout=30,
    )
    if r.status_code not in [200, 202]:
        raise APIError("TriggerRefresh", r.status_code, r.text, dict(r.headers), url)
