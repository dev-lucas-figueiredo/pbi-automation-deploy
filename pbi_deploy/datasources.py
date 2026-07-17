"""Leitura das planilhas de entrada e geracao do SQL de user_dashboards.

Fonte de dados do pipeline:
    lideres_projeto.xlsx    mapeamento lider -> doacao (define os paineis).
    refresh_schedule.xlsx   horarios de refresh por lider.
    user_dashboards.xlsx    credenciais/URLs para gerar o SQL de carga.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.panel import Panel
from rich.text import Text

from . import config
from .console import console


def _normalizar_doacao(valor):
    """Aplica a mesma normalizacao da coluna dDoação.DOAÇÃO no modelo.

    O modelo usa Text.Upper(Text.Trim(Text.Clean(...))): remove caracteres de
    controle, apara as pontas e coloca em maiuscula. Replicamos exatamente para
    que os valores do mapeamento casem com os do modelo no filtro do painel.
    """
    s = "".join(ch for ch in str(valor) if ord(ch) >= 32)
    return s.strip().upper()


def carregar_lideres_doacoes():
    """
    Le data/lideres_projeto.xlsx e retorna dict {lider: [doacoes]}.

    Uma linha por lider; a coluna doacao traz as doacoes separadas por
    virgula. Linhas com lider ou doacao vazios sao ignoradas. As doacoes sao
    normalizadas para casar com dDoação.DOAÇÃO e deduplicadas preservando a
    ordem de leitura.
    """
    df = pd.read_excel(config.LIDERES_PROJETO_PATH, dtype=str)

    for col in ("lider", "doacao"):
        if col not in df.columns:
            raise Exception(f"Coluna '{col}' ausente em {config.LIDERES_PROJETO_PATH}")

    lideres = {}
    for _, row in df.iterrows():
        lider = str(row.get("lider", "")).strip()
        doacoes_raw = str(row.get("doacao", "")).strip()
        if not lider or lider.lower() == "nan":
            continue
        if not doacoes_raw or doacoes_raw.lower() == "nan":
            continue

        doacoes = []
        for parte in doacoes_raw.split(","):
            doacao = _normalizar_doacao(parte)
            if doacao and doacao != "NAN" and doacao not in doacoes:
                doacoes.append(doacao)
        if doacoes:
            lideres[lider] = doacoes
    return lideres


def carregar_schedule():
    """
    Le refresh_schedule.xlsx e retorna dict {lider: [horarios]}.
    Lideres com celula 'horarios' vazia sao ignorados (sem agendamento).
    Fallback para horarios padrao se o lider nao estiver na planilha.
    Aceita a coluna nova 'lider' ou a antiga 'gestor' (compatibilidade).
    """
    df = pd.read_excel(config.REFRESH_SCHEDULE_PATH, dtype=str)
    coluna_chave = "lider" if "lider" in df.columns else "gestor"
    schedule = {}
    for _, row in df.iterrows():
        chave = str(row.get(coluna_chave, "")).strip()
        horarios_raw = str(row.get("horarios", "")).strip()
        if not chave or chave.lower() == "nan":
            continue
        if not horarios_raw or horarios_raw.lower() in ("nan", ""):
            schedule[chave] = []  # vazio = sem agendamento automatico
        else:
            horarios = [h.strip() for h in horarios_raw.split(",") if h.strip()]
            schedule[chave] = horarios
    return schedule


def gerar_sql_user_dashboards():
    """
    Le data/user_dashboards.xlsx e gera sql/carga_user_dashboards.sql
    no formato upsert_user_dashboard com criptografia de url_painel.
    """
    console.print()
    console.print(
        Panel(
            Text.assemble(
                ("ETAPA FINAL / GERACAO SQL\n", "bold white"),
                ("Origem: data/user_dashboards.xlsx  →  Destino: sql/carga_user_dashboards.sql", "dim"),
            ),
            border_style="cyan",
            padding=(0, 2),
        )
    )

    if not config.URL_ENCRYPTION_KEY:
        raise Exception("URL_ENCRYPTION_KEY ausente no .env")

    df = pd.read_excel(config.USER_DASHBOARDS_PATH, dtype=str)

    colunas_obrigatorias = ["usuario", "senha", "url_painel"]
    for col in colunas_obrigatorias:
        if col not in df.columns:
            raise Exception(f"Coluna '{col}' ausente em {config.USER_DASHBOARDS_PATH}")

    df = df.dropna(subset=colunas_obrigatorias)
    if df.empty:
        raise Exception(f"Nenhum registro valido em {config.USER_DASHBOARDS_PATH}")

    linhas = []
    for _, row in df.iterrows():
        usuario = str(row["usuario"]).replace("'", "''")
        senha = str(row["senha"]).replace("'", "''")
        url = str(row["url_painel"]).replace("'", "''")
        linhas.append(
            f"SELECT public.upsert_user_dashboard(\n"
            f"  '{usuario}',\n"
            f"  '{senha}',\n"
            f"  '{url}',\n"
            f"  current_setting('app.url_key')\n"
            f");"
        )

    chamadas_sql = "\n\n".join(linhas)
    sql = f"""-- =============================================================================
-- Envio em lote de user_dashboards (com criptografia da url_painel)
-- Gerado automaticamente pelo pipeline de deploy em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- =============================================================================

BEGIN;

-- Define a chave de criptografia para esta sessão (não persiste).
SELECT set_config('app.url_key', '{config.URL_ENCRYPTION_KEY}', true);

-- ---- Lote de usuários -------------------------------------------------------

{chamadas_sql}

COMMIT;

-- =============================================================================
-- Conferência opcional (NÃO mostra a URL em texto — apenas usuários gravados):
--   SELECT usuario FROM public.user_dashboards ORDER BY usuario;
-- =============================================================================
"""

    sql_path = Path(config.SQL_DIR) / "carga_user_dashboards.sql"
    ja_existia = sql_path.exists()
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql)

    acao = "[dim]atualizado[/dim]" if ja_existia else "[green]criado[/green]"
    console.print(f"  Arquivo SQL {acao}: {sql_path}  ({len(df)} registros)\n")
