# AGENTS.md — Guia para agentes de IA

Este arquivo é a fonte de verdade para qualquer agente de IA (Claude, Copilot,
Cursor etc.) que for editar este repositório. Leia antes de propor mudanças.

## O que é este projeto

Pipeline de publicação Power BI / Microsoft Fabric. Clona um template `.pbip`,
gera um modelo semântico + relatório por gestão, publica no Fabric e configura
agendamento/refresh. Usuário final só executa `run_deploy.bat` — sem CLI, sem
parâmetros, sem passos manuais.

Visão geral e arquitetura estão no [README.md](README.md); detalhes de uso
(planilhas, `.env`, fases do pipeline) estão no [USAGE.md](USAGE.md). Este
arquivo trata de **como editar o código**.

## Risco real — leia antes de executar

`pbi_deploy.main` faz deploy de verdade em um workspace Fabric/Power BI de
produção e dispara refresh real dos datasets. **Não execute o pipeline
fim-a-fim ("python -m pbi_deploy.main" ou o `.bat`) para validar uma mudança**
a menos que o usuário peça explicitamente. Para validar alterações, prefira:

```bat
env\Scripts\python.exe -c "import ast; ast.parse(open('pbi_deploy/arquivo.py', encoding='utf-8').read())"
env\Scripts\python.exe -c "import pbi_deploy.main"
```

Isso garante sintaxe e imports corretos sem tocar a API real. Não existe
suíte de testes automatizados neste projeto — não invente uma sem alinhar
com o usuário.

## Arquitetura

Pacote `pbi_deploy/`, uma responsabilidade por módulo:

```
pbi_deploy/
├── main.py            Entrypoint (python -m pbi_deploy.main). Chamado pelo .bat.
├── config.py           Env vars (.env), caminhos, constantes. Sem imports internos.
├── console.py          Console rich compartilhado, mask(), banner(). Sem imports internos.
├── errors.py            APIError, parse_body_safe(). Sem imports internos.
├── auth.py              Azure AD: token de app (SPN) e token delegado (ROPC).
├── fabric.py             Fabric Items API: listar itens, build payload, criar/atualizar, poll_lro.
├── powerbi.py            Power BI REST: TakeOver, credenciais SharePoint, refresh schedule/trigger.
├── builder.py            Clona template -> build/, injeta filtro de gestão, fixa referência do dataset.
├── datasources.py        Lê planilhas (schedule) e gera sql/carga_user_dashboards.sql.
├── prerequisites.py      Etapa 0: valida .env, templates, planilhas, cria pastas.
├── runner.py             executar_fase(): loop genérico com progress bar + tabela + log por item.
└── pipeline.py           Orquestra as fases em main()/run(); único módulo que conhece a ordem completa.
```

Regra de dependência: `config`, `console` e `errors` são a camada base e
**nunca** importam outro módulo do pacote — evita ciclos. Todo o resto pode
importar a camada base e os módulos de domínio (`fabric`, `powerbi`,
`builder`, `datasources`), mas só `pipeline.py` conhece a sequência completa
das fases.

## Onde alterar o quê

- **Nova chamada à Fabric Items API** → `fabric.py`.
- **Nova chamada à Power BI REST API** (datasets, refresh, gateways) → `powerbi.py`.
- **Mudança na regra de geração do relatório por gestão** (filtro, consolidado
  GFP/KFW) → `builder.py` (`clone_and_compile`).
- **Nova fase no pipeline** → defina a função `processar_um` em `pipeline.py`
  e chame `runner.executar_fase(...)`; não duplique a lógica de
  progresso/tabela/log que já existe em `runner.py`.
- **Nova planilha de entrada ou export SQL** → `datasources.py`.
- **Nova variável de ambiente** → adicione em `config.py` e valide em
  `prerequisites.py` se for obrigatória.

## Convenções do código

- Strings voltadas ao usuário (banners, tabelas, mensagens de erro) e
  docstrings são em **português**, seguindo o padrão já existente. Não troque
  para inglês em código novo.
- Comentários só quando explicam um *porquê* não óbvio (ex.: por que o schema
  PBIR exige `byConnection` e não `byItemId` — ver `builder.py`). Não
  comente o que o código já deixa claro pelo nome.
- Sem abstrações novas "para o futuro". Se três funções fizerem algo
  parecido, isso não é motivo automático para criar uma classe/base — siga o
  padrão funcional já usado no pacote.
- Erros de API sempre como `errors.APIError`, nunca `Exception` genérica, para
  manter o diagnóstico estruturado (`status_code`, `headers`, `action`).
- Segredos só em `.env` (nunca hardcoded, nunca commitados). `.env` já está no
  `.gitignore`.

## Pontos de atenção herdados do código original

- `auth.get_delegated_token` e `powerbi.configurar_credenciais_sharepoint`
  existem mas **não são chamados** no fluxo principal de `pipeline.py` (a
  configuração de credenciais SharePoint é feita fora deste script hoje). Não
  remova sem confirmar com o usuário — pode ser um próximo passo planejado.
- O consolidado `"GFP e KFW"` é um caso especial em `builder.clone_and_compile`
  e em `pipeline._identificar_gestores`: agrupa o gestor `GFP` com todos os
  gestores cujo nome começa com `KFW`. Qualquer mudança na regra de
  agrupamento precisa refletir nos dois lugares.
- `gestao_areas.xlsx` ignora linhas onde `RESPONSAVEL == SUPERINTENDÊNCIA`
  (ver `pipeline._identificar_gestores`) — não é bug, é filtro intencional.
