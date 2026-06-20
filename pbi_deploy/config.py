"""Configuracao central do pipeline: credenciais, caminhos e constantes.

Toda configuracao mutavel vem do arquivo .env. Os demais modulos importam
daqui para nao reler variaveis de ambiente nem repetir caminhos.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Credenciais e identificadores (lidos do .env) ---------------------------
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
URL_ENCRYPTION_KEY = os.getenv("URL_ENCRYPTION_KEY")

# Conta delegada (ROPC). Opcional: usada apenas no fluxo de credenciais SharePoint.
DELEGATED_USER = os.getenv("DELEGATED_USER")
DELEGATED_PASSWORD = os.getenv("DELEGATED_PASSWORD")

# --- Identidade do projeto ---------------------------------------------------
PBI_PROJECT_NAME = "Painel Financeiro Executivo"

# --- Diretorios --------------------------------------------------------------
TEMPLATE_DIR = "template"
BUILD_DIR = "build"
LOG_DIR = "logs"
SQL_DIR = "sql"

# --- Planilhas de entrada ----------------------------------------------------
EXCEL_FILE_PATH = os.path.join("data", "gestao_areas.xlsx")
REFRESH_SCHEDULE_PATH = os.path.join("data", "refresh_schedule.xlsx")
USER_DASHBOARDS_PATH = os.path.join("data", "user_dashboards.xlsx")

# --- Artefatos base do template ----------------------------------------------
BASE_SEMANTIC_MODEL = os.path.join(TEMPLATE_DIR, f"{PBI_PROJECT_NAME}.SemanticModel")
BASE_REPORT = os.path.join(TEMPLATE_DIR, f"{PBI_PROJECT_NAME}.Report")

# --- Endpoints e autenticacao ------------------------------------------------
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else None
SCOPE_PBI = ["https://analysis.windows.net/powerbi/api/.default"]
SCOPE = SCOPE_PBI  # alias mantido para compatibilidade
PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
