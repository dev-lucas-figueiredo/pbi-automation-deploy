"""Configuracao central do pipeline: credenciais, caminhos e constantes.

Toda configuracao mutavel vem do arquivo .env. Os demais modulos importam
daqui para nao reler variaveis de ambiente nem repetir caminhos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
URL_ENCRYPTION_KEY = os.getenv("URL_ENCRYPTION_KEY")

# Conta delegada (ROPC). Opcional: usada apenas no fluxo de credenciais SharePoint.
DELEGATED_USER = os.getenv("DELEGATED_USER")
DELEGATED_PASSWORD = os.getenv("DELEGATED_PASSWORD")

TEMPLATE_DIR = "template"
BUILD_DIR = "build"
LOG_DIR = "logs"
SQL_DIR = "sql"


def descobrir_template(template_dir):
    """Localiza o par SemanticModel + Report dentro de `template_dir`.

    Devolve (semantic_model, report, erro). Em caso de problema (zero ou mais
    de um par, nomes-base diferentes) os dois caminhos vem como None e `erro`
    traz uma mensagem listando o que foi encontrado. Nunca levanta excecao,
    pois roda no import do modulo; quem reporta o erro e prerequisites.py.
    """
    pasta = Path(template_dir)
    modelos = sorted(p.name for p in pasta.glob("*.SemanticModel") if p.is_dir())
    relatorios = sorted(p.name for p in pasta.glob("*.Report") if p.is_dir())

    if len(modelos) != 1 or len(relatorios) != 1:
        return None, None, (
            f"Esperada exatamente 1 pasta *.SemanticModel e 1 *.Report em {template_dir}/. "
            f"Encontrado: SemanticModel={modelos or 'nenhuma'}, Report={relatorios or 'nenhuma'}"
        )

    base_modelo = modelos[0][: -len(".SemanticModel")]
    base_relatorio = relatorios[0][: -len(".Report")]
    if base_modelo != base_relatorio:
        return None, None, (
            f"Os nomes-base do template nao coincidem: '{modelos[0]}' e '{relatorios[0]}'"
        )

    return str(pasta / modelos[0]), str(pasta / relatorios[0]), None


def extrair_nome_template(caminho_modelo):
    """Extrai o nome-base do template a partir da pasta .SemanticModel."""
    if not caminho_modelo:
        return None
    nome = Path(caminho_modelo).name
    if nome.endswith(".SemanticModel"):
        return nome[: -len(".SemanticModel")]
    return nome


BASE_SEMANTIC_MODEL, BASE_REPORT, TEMPLATE_ERRO = descobrir_template(TEMPLATE_DIR)
TEMPLATE_BASE_NAME = extrair_nome_template(BASE_SEMANTIC_MODEL)

# Prefixo dos itens publicados no workspace e gerados no build/.
# Vem sempre exclusivamente do nome-base do template descoberto em template/.
PBI_PUBLISHED_NAME = TEMPLATE_BASE_NAME

# Notificacao por e-mail de falha do refresh agendado. SPN so suporta
# NoNotification; MailOnFailure exige o token delegado (ver powerbi.py).
NOTIFY_OPTIONS_VALIDAS = ("MailOnFailure", "NoNotification")
_notify_bruto = os.getenv("REFRESH_NOTIFY_OPTION", "MailOnFailure").strip()
# Valor invalido e mantido como veio para prerequisites.py reportar o erro.
REFRESH_NOTIFY_OPTION = next(
    (o for o in NOTIFY_OPTIONS_VALIDAS if o.lower() == _notify_bruto.lower()), _notify_bruto
)

# Planilha unica de dados de entrada do pipeline (nunca versionada no git)
EXCEL_INPUT_PATH = os.path.join("data", "dados_entrada.xlsx")

# Nomes padronizados das abas na planilha unica de entrada
SHEET_GESTAO_AREAS = "Gestão - Áreas"
SHEET_GESTAO_SCHEDULE = "Gestão - Agendamento"
SHEET_GESTAO_USUARIOS = "Gestão - Usuários"

SHEET_LIDERES_DOACOES = "Líderes - Doações"
SHEET_LIDERES_SCHEDULE = "Líderes - Agendamento"
SHEET_LIDERES_USUARIOS = "Líderes - Usuários"

# Mapeamentos de abas por modo
SCHEDULE_ABAS = {
    "gestao": SHEET_GESTAO_SCHEDULE,
    "lideres": SHEET_LIDERES_SCHEDULE,
}

USER_DASHBOARDS_ABAS = {
    "gestao": SHEET_GESTAO_USUARIOS,
    "lideres": SHEET_LIDERES_USUARIOS,
}

# Aliases de compatibilidade
EXCEL_FILE_PATH = EXCEL_INPUT_PATH
REFRESH_SCHEDULE_PATH = EXCEL_INPUT_PATH
LIDERES_PROJETO_PATH = EXCEL_INPUT_PATH
LIDERES_REFRESH_SCHEDULE_PATH = EXCEL_INPUT_PATH
USER_DASHBOARDS_PATH = EXCEL_INPUT_PATH

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else None
SCOPE_PBI = ["https://analysis.windows.net/powerbi/api/.default"]
SCOPE = SCOPE_PBI  # alias mantido para compatibilidade
PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
