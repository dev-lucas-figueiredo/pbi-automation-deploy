"""Autenticacao no Azure AD: Service Principal (SPN) e fluxo delegado (ROPC)."""

import sys
import time

import msal
import requests
from rich.table import Table
from rich import box

from . import config
from .console import console, mask, banner


def autenticar_azure():
    """Obtem token de aplicacao (client credentials) e exibe o resumo da sessao."""
    banner(
        "ETAPA 1 / AUTENTICACAO AZURE AD",
        f"Authority: {config.AUTHORITY}",
        cor="bright_blue",
    )

    info = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    info.add_column(style="dim cyan")
    info.add_column(style="white")
    info.add_row("Tenant ID", mask(config.TENANT_ID))
    info.add_row("Client ID", mask(config.CLIENT_ID))
    info.add_row("Client Secret", mask(config.CLIENT_SECRET))
    info.add_row("Scope", config.SCOPE[0])
    info.add_row("Fluxo", "Client Credentials (Service Principal)")
    console.print(info)

    t0 = time.time()
    with console.status("[bold yellow]Solicitando token ao Azure AD...", spinner="dots"):
        try:
            app = msal.ConfidentialClientApplication(
                config.CLIENT_ID,
                authority=config.AUTHORITY,
                client_credential=config.CLIENT_SECRET,
            )
            result = app.acquire_token_for_client(scopes=config.SCOPE)
        except Exception as e:
            console.print(f"\n[red bold]Falha critica no MSAL:[/red bold] {e}\n")
            sys.exit(1)
    elapsed = time.time() - t0

    if "access_token" not in result:
        erro = result.get("error", "?")
        descr = result.get("error_description", "sem descricao")
        correlation = result.get("correlation_id", "")
        console.print(
            f"\n[red bold]Autenticacao recusada.[/red bold] error={erro}\n"
            f"correlation_id={correlation}\n{descr}\n"
        )
        sys.exit(1)

    token = result["access_token"]
    expires_in = result.get("expires_in", 0)

    resumo = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    resumo.add_column(style="dim cyan")
    resumo.add_column(style="white")
    resumo.add_row("Status", "[green bold]Token obtido[/green bold]")
    resumo.add_row("Tempo de resposta", f"{elapsed:.2f}s")
    resumo.add_row("Token type", result.get("token_type", "Bearer"))
    resumo.add_row("Validade", f"{expires_in}s  ({expires_in // 60} min)")
    resumo.add_row("Token (preview)", f"{token[:18]}...{token[-8:]}")
    console.print(resumo)

    return token


def get_delegated_token():
    """
    Obtem token OAuth2 delegado via ROPC (Resource Owner Password Credentials)
    usando email e senha da conta de servico. Requer que a conta nao tenha MFA.
    Usado para configurar credenciais de datasource SharePoint via API Power BI,
    operacao que exige contexto de usuario humano, nao de Service Principal.
    """
    url = f"https://login.microsoftonline.com/{config.TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "password",
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET,
        "username": config.DELEGATED_USER,
        "password": config.DELEGATED_PASSWORD,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    }
    r = requests.post(url, data=data, timeout=30)
    if r.status_code != 200:
        raise Exception(
            f"Falha ao obter token delegado: HTTP {r.status_code} | {r.text[:300]}"
        )
    result = r.json()
    if "access_token" not in result:
        raise Exception(
            f"Token delegado ausente na resposta: {result.get('error_description', result)}"
        )
    return result["access_token"]
