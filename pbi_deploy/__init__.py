"""Pipeline de publicacao de modelos e relatorios Power BI / Microsoft Fabric.

Pacote modular do deploy. O ponto de entrada para o usuario final e
`pbi_deploy/main.py` (chamado pelo run_deploy.bat via `python -m
pbi_deploy.main`), que apenas delega para `pbi_deploy.pipeline.run`.

Mapa de modulos:
    main           Entrypoint executavel (python -m pbi_deploy.main).
    config         Configuracao: variaveis de ambiente, caminhos e constantes.
    console        Saida visual (rich): console, mascaramento e banners.
    errors         APIError e utilitarios de parsing de resposta.
    auth           Autenticacao no Azure AD (Service Principal e delegado).
    fabric         Cliente da Fabric Items API (listar, criar e atualizar itens).
    powerbi        Operacoes da Power BI REST API sobre datasets.
    builder        Clonagem e compilacao dos artefatos .pbip por lider de projeto.
    datasources    Leitura das planilhas de entrada e geracao de SQL.
    prerequisites  Validacao de pre-requisitos antes da execucao.
    runner         Executor generico de uma fase do pipeline.
    pipeline       Orquestracao das fases (main / run).

Consulte AGENTS.md (raiz do projeto) para convencoes de trabalho com agentes de IA.
"""

__all__ = ["main"]


def main():
    """Atalho para o ponto de entrada do pipeline."""
    from .pipeline import main as _main

    return _main()
