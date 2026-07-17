"""Cliente da Fabric Items API: inspecao do workspace e upload de itens.

Cobre os endpoints `https://api.fabric.microsoft.com/v1/workspaces/...`:
listar itens, montar o payload de definicao (InlineBase64), criar/atualizar
itens e aguardar Long Running Operations (LRO).
"""

import base64
import json
import os
import sys
import time

import requests
from rich.table import Table
from rich import box

from . import config
from .console import console, mask, banner
from .errors import APIError, parse_body_safe


def listar_itens_workspace(token, titulo="ETAPA 2 / INSPECAO DO WORKSPACE"):
    """Lista os itens do workspace e imprime a contagem por tipo."""
    banner(titulo, f"Workspace ID: {mask(config.WORKSPACE_ID)}", cor="bright_blue")

    url = f"{config.FABRIC_API_BASE}/workspaces/{config.WORKSPACE_ID}/items"
    headers = {"Authorization": f"Bearer {token}"}

    t0 = time.time()
    with console.status("[yellow]Consultando Fabric API...", spinner="dots"):
        response = requests.get(url, headers=headers)
    elapsed = time.time() - t0

    if response.status_code != 200:
        console.print(
            f"[red bold]Falha ao listar itens.[/red bold] "
            f"HTTP {response.status_code} | body: {response.text[:300]}\n"
        )
        sys.exit(1)

    items = response.json().get("value", [])

    tipos = {}
    for item in items:
        t = item.get("type", "?")
        tipos[t] = tipos.get(t, 0) + 1

    tabela = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    tabela.add_column("Tipo de item", style="white")
    tabela.add_column("Quantidade", justify="right", style="cyan")
    for tipo, qtd in sorted(tipos.items(), key=lambda x: -x[1]):
        tabela.add_row(tipo, str(qtd))
    tabela.add_row("[bold]TOTAL[/bold]", f"[bold]{len(items)}[/bold]")
    console.print(tabela)
    console.print(f"[dim]Resposta em {elapsed:.2f}s | endpoint: items[/dim]")

    return items


def build_definition_payload(folder_path):
    """Empacota todos os arquivos de uma pasta como partes InlineBase64."""
    parts = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, folder_path).replace("\\", "/")
            with open(full_path, "rb") as f:
                content = f.read()
            parts.append(
                {
                    "path": rel_path,
                    "payload": base64.b64encode(content).decode("utf-8"),
                    "payloadType": "InlineBase64",
                }
            )
    return {"definition": {"parts": parts}}


def poll_lro(token, location_url, max_attempts=20, wait_seconds=2):
    """
    Aguarda Long Running Operation concluir e tenta retornar o ID do item criado.
    Retorna None se nao conseguir resolver dentro do limite, sem quebrar a execucao.
    """
    if not location_url:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(max_attempts):
        time.sleep(wait_seconds)
        try:
            r = requests.get(location_url, headers=headers, timeout=15)
        except requests.RequestException:
            continue

        if r.status_code == 202:
            # Operacao ainda em andamento, continua o polling
            continue

        body = parse_body_safe(r) or {}
        status = (body.get("status") or "").lower()

        if status in ("succeeded", "completed", "success"):
            result_url = r.headers.get("Location") or body.get("resultUrl")
            if result_url and result_url != location_url:
                try:
                    rr = requests.get(result_url, headers=headers, timeout=15)
                    result_body = parse_body_safe(rr) or {}
                    return result_body.get("id") or body.get("id")
                except requests.RequestException:
                    return body.get("id")
            return body.get("id")

        if status == "failed":
            raise APIError(
                "LRO falhou",
                r.status_code,
                json.dumps(body, ensure_ascii=False),
                dict(r.headers),
                location_url,
            )
    return None


def upload_item_to_fabric(token, display_name, item_type, folder_path, existing_items):
    """Cria ou atualiza um item (SemanticModel/Report) e retorna (status, id)."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload_definition = build_definition_payload(folder_path)
    matched_item = next(
        (i for i in existing_items if i["displayName"] == display_name and i["type"] == item_type),
        None,
    )

    if matched_item:
        item_id = matched_item["id"]
        url = f"{config.FABRIC_API_BASE}/workspaces/{config.WORKSPACE_ID}/items/{item_id}/updateDefinition"
        response = requests.post(url, headers=headers, json=payload_definition)
        if response.status_code not in [200, 202]:
            raise APIError("Atualizar", response.status_code, response.text, dict(response.headers), url)
        return "Atualizado", item_id

    # Caminho de criacao
    url = f"{config.FABRIC_API_BASE}/workspaces/{config.WORKSPACE_ID}/items"
    payload_creation = {
        "displayName": display_name,
        "type": item_type,
        "definition": payload_definition["definition"],
    }
    response = requests.post(url, headers=headers, json=payload_creation)

    if response.status_code not in [201, 202]:
        raise APIError("Criar", response.status_code, response.text, dict(response.headers), url)

    body = parse_body_safe(response)
    location = response.headers.get("Location", "")

    # Caso A: 201 Created com body JSON contendo o id (criacao sincrona)
    if response.status_code == 201 and body and body.get("id"):
        return "Criado", body["id"]

    # Caso B: 202 Accepted com Location header (LRO assincrona, body geralmente 'null')
    if response.status_code == 202 and location:
        final_id = poll_lro(token, location)
        if final_id:
            return "Criado (LRO)", final_id
        return "Criado (LRO sem id)", None

    # Caso C: 201/202 com body vazio ou null e sem Location utilizavel
    # Item provavelmente foi criado, mas nao conseguimos resolver o ID nesta resposta
    return "Criado (sem id)", None
