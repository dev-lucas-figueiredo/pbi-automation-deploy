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

# Prefixo dos itens publicados no workspace. Independe do nome do arquivo do
# template: o upload casa itens por displayName, entao mudar este valor cria
# itens novos em vez de atualizar os existentes.
PBI_PUBLISHED_NAME = os.getenv("PBI_PUBLISHED_NAME", "Painel Financeiro Executivo")

# Notificacao por e-mail de falha do refresh agendado. SPN so suporta
# NoNotification; MailOnFailure exige o token delegado (ver powerbi.py).
NOTIFY_OPTIONS_VALIDAS = ("MailOnFailure", "NoNotification")
_notify_bruto = os.getenv("REFRESH_NOTIFY_OPTION", "MailOnFailure").strip()
# Valor invalido e mantido como veio para prerequisites.py reportar o erro.
REFRESH_NOTIFY_OPTION = next(
    (o for o in NOTIFY_OPTIONS_VALIDAS if o.lower() == _notify_bruto.lower()), _notify_bruto
)

TEMPLATE_DIR = "template"
BUILD_DIR = "build"
LOG_DIR = "logs"
SQL_DIR = "sql"

# Modo gestao: painel por RESPONSAVEL (dGestão).
EXCEL_FILE_PATH = os.path.join("data", "gestao_areas.xlsx")
REFRESH_SCHEDULE_PATH = os.path.join("data", "refresh_schedule_gestao.xlsx")

# Modo lideres: painel por doacoes do lider (dDoação).
LIDERES_PROJETO_PATH = os.path.join("data", "lideres_projeto.xlsx")
LIDERES_REFRESH_SCHEDULE_PATH = os.path.join("data", "refresh_schedule_lideres.xlsx")

# Cadastro de usuarios do Lovable: editado no OneDrive da FAS, baixado para
# data/ antes do deploy. Nunca versionado (contem credenciais). Uma aba por modo.
USER_DASHBOARDS_PATH = os.path.join(
    "data", "Cadastro de usuários Lovable - Painel Financeiro Executivo.xlsx"
)
USER_DASHBOARDS_ABAS = {
    "gestao": "Gestão - Lista de Usuários",
    "lideres": "Líder - Lista de Usuários",
}



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


BASE_SEMANTIC_MODEL, BASE_REPORT, TEMPLATE_ERRO = descobrir_template(TEMPLATE_DIR)

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else None
SCOPE_PBI = ["https://analysis.windows.net/powerbi/api/.default"]
SCOPE = SCOPE_PBI  # alias mantido para compatibilidade
PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
