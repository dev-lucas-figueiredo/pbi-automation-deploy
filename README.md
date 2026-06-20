# Pipeline de Publicação — Painel Financeiro Executivo

Automação que clona um template Power BI (`.pbip`), gera um painel por gestão e
publica tudo no Microsoft Fabric, configurando agendamento e disparo de refresh.

> **Novo aqui?** Leia o [USAGE.md](USAGE.md) — guia completo de como preparar
> os arquivos e executar o pipeline.

---

## Para o usuário final

Basta dar **duplo clique** em **`run_deploy.bat`**. Detalhes completos sobre
preparação de arquivos, planilhas e template estão no [USAGE.md](USAGE.md).

---

## Configuração (`.env`)

```env
TENANT_ID=...
CLIENT_ID=...
CLIENT_SECRET=...
WORKSPACE_ID=...
URL_ENCRYPTION_KEY=...
# Opcionais (fluxo delegado de credenciais SharePoint):
DELEGATED_USER=...
DELEGATED_PASSWORD=...
```

> O `.env` contém segredos e **não** deve ser versionado (já está no `.gitignore`).

---

## Planilhas de entrada (`data/`)

| Arquivo                  | Obrigatório | Função                                                        |
| ------------------------ | :---------: | ------------------------------------------------------------- |
| `gestao_areas.xlsx`      |     Sim     | Lista de gestores (coluna `RESPONSAVEL`).                     |
| `refresh_schedule.xlsx`  |     Sim     | Horários de refresh por gestor (`gestor`, `horarios`).        |
| `user_dashboards.xlsx`   |     Não     | Gera `sql/carga_user_dashboards.sql` (usuário, senha, URL).   |

> Colunas obrigatórias, exemplos e regras especiais: ver [USAGE.md § 5](USAGE.md#5-planilhas-de-entrada-pasta-data).

---

## O que o pipeline faz

| Etapa / Fase | Descrição                                                                 |
| ------------ | ------------------------------------------------------------------------- |
| Etapa 0      | Valida credenciais, templates e planilhas.                                |
| Etapa 1      | Autentica no Azure AD (Service Principal).                                 |
| Etapa 2      | Inspeciona os itens existentes no workspace.                              |
| Fase 1       | Clona o template e publica um **modelo semântico** por gestão.            |
| Fase 2       | Publica os **relatórios** vinculados ao modelo correspondente.            |
| Fase 3       | Pós-deploy: TakeOver, agendamento e disparo de refresh inicial.           |
| Final        | Resumo executivo, log estruturado em `logs/` e geração de SQL.            |

Resultados ficam em `build/` (artefatos), `logs/` (JSON por execução) e `sql/`.

---

## Arquitetura do código

A lógica é um pacote modular. O `.bat` chama `pbi_deploy/main.py` (via
`python -m pbi_deploy.main`), que apenas delega para o orquestrador. Cada
módulo tem uma responsabilidade única — desenho pensado para manutenção,
inclusive por agentes de IA. Detalhes de convenções para agentes estão em
[AGENTS.md](AGENTS.md).

```
run_deploy.bat            Entrada do usuário final (ativa venv + roda o pipeline).

pbi_deploy/
├── __init__.py           Documentação do pacote e atalho main().
├── main.py               Entrypoint fino: delega para pbi_deploy.pipeline.run.
├── config.py             Variáveis de ambiente, caminhos e constantes.
├── console.py            Console rich compartilhado, mask() e banner().
├── errors.py             APIError e parsing seguro de respostas.
├── auth.py               Autenticação Azure AD (Service Principal e delegado).
├── fabric.py             Fabric Items API: listar, criar/atualizar, poll LRO.
├── powerbi.py            Power BI REST: TakeOver, schedule, refresh, SharePoint.
├── builder.py            Clonagem/compilação dos artefatos .pbip por gestão.
├── datasources.py        Leitura das planilhas e geração de SQL.
├── prerequisites.py      Validação de pré-requisitos (Etapa 0).
├── runner.py             Executor genérico de uma fase (progresso + tabela).
└── pipeline.py           Orquestração das fases (main / run).
```

### Fluxo de dependências

```
pipeline → prerequisites, auth, fabric, powerbi, builder, datasources, runner
        ↓
     config, console, errors   (camada base, sem dependências internas)
```

`config`, `console` e `errors` não importam outros módulos do pacote, evitando
ciclos. Para adicionar uma chamada de API, edite `fabric.py` ou `powerbi.py`;
para uma nova fase, use `runner.executar_fase` dentro de `pipeline.py`.

---

## Execução manual (desenvolvimento)

```bat
env\Scripts\activate
pip install -r requirements.txt
python -m pbi_deploy.main
```

## Códigos de saída

| Código | Significado                          |
| :----: | ------------------------------------ |
| `0`    | Sucesso (todas as fases sem falha).  |
| `1`    | Concluído com falhas em alguma fase. |
| `2`    | Erro fatal não tratado.              |
| `130`  | Interrompido pelo usuário (Ctrl+C).  |
