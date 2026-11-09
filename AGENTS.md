# AGENTS.md: Guia para agentes de IA

Este arquivo é a fonte de verdade para qualquer agente de IA (Claude, Copilot,
Cursor etc.) que for editar este repositório. Leia antes de propor mudanças.

## O que é este projeto

Pipeline de publicação Power BI / Microsoft Fabric. Clona um template `.pbip`,
gera um modelo semântico + relatório por unidade, publica no Fabric e configura
agendamento/refresh. Há **dois modos**, cada um com seu `.bat`:

- **gestao** (`run_deploy_gestao.bat`): 1 painel por gestão, filtro
  `dGestão.RESPONSAVEL` (com o consolidado especial GFP+KFW). Fonte:
  aba `Gestão - Áreas` em `data/dados_entrada.xlsx`.
- **lideres** (`run_deploy_lideres.bat`): 1 painel por líder de projeto, filtro
  `dDoação.DOAÇÃO` com as doações daquele líder. Fonte:
  aba `Líderes - Doações` em `data/dados_entrada.xlsx`.

O modo é passado como argumento (`python -m pbi_deploy.main <gestao|lideres>`);
o usuário final só dá duplo clique no `.bat` do modo desejado, sem CLI.

Visão geral e arquitetura estão no [README.md](README.md); detalhes de uso
(planilhas, `.env`, fases do pipeline) estão no [USAGE.md](USAGE.md). Este
arquivo trata de **como editar o código**.

## Risco real: leia antes de executar

`pbi_deploy.main` faz deploy de verdade em um workspace Fabric/Power BI de
produção e dispara refresh real dos datasets. **Não execute o pipeline
fim-a-fim ("python -m pbi_deploy.main" ou o `.bat`) para validar uma mudança**
a menos que o usuário peça explicitamente. Para validar alterações, prefira:

```bat
env\Scripts\python.exe -c "import ast; ast.parse(open('pbi_deploy/arquivo.py', encoding='utf-8').read())"
env\Scripts\python.exe -c "import pbi_deploy.main"
```

Rodar `python -m pbi_deploy.main` sem argumento (ou com modo inválido) só imprime
o uso e sai com código 2, sem tocar a API, então é seguro para checar o parse dos
argumentos.

Isso garante sintaxe e imports corretos sem tocar a API real. Há também uma
suíte mínima de testes unitários em `tests/` (pytest, sem acesso à API: HTTP
simulado e templates em pasta temporária). `pytest` não está no `env/` de
produção (que é versionado e vai para o usuário final); instale com
`pip install -r requirements-dev.txt` em um ambiente próprio e rode `pytest`.
Rode-a depois de mexer em `config.py`, `builder.py`, `powerbi.py` ou `pipeline.py`.

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
├── builder.py            Clona template -> build/, injeta filtro (gestão ou líder), fixa referência do dataset.
├── datasources.py        Lê planilhas (líderes/doações, schedule) e gera sql/carga_user_dashboards_<modo>.sql.
├── prerequisites.py      Etapa 0: valida .env, template, planilhas (por modo), cria pastas.
├── runner.py             executar_fase(): loop genérico com progress bar + tabela + log por item.
└── pipeline.py           Orquestra as fases em main(mode)/run(mode); conhece a ordem completa e os dois modos.

tests/                 Testes unitários (pytest): template, nomes publicados, responsáveis, notifyOption.
```

Regra de dependência: `config`, `console` e `errors` são a camada base e
**nunca** importam outro módulo do pacote, o que evita ciclos. Todo o resto pode
importar a camada base e os módulos de domínio (`fabric`, `powerbi`,
`builder`, `datasources`), mas só `pipeline.py` conhece a sequência completa
das fases.

## Onde alterar o quê

- **Nova chamada à Fabric Items API** → `fabric.py`.
- **Nova chamada à Power BI REST API** (datasets, refresh, gateways) → `powerbi.py`.
- **Mudança na regra do relatório por gestão** (filtro RESPONSAVEL, caso GFP+KFW)
  → `builder.py` (`clone_and_compile_gestao`, `_responsaveis_da_gestao`,
  `_montar_filtro_responsavel`) e `pipeline._identificar_gestores`.
- **Descoberta do template / nome publicado** → `config.descobrir_template` e
  `config.PBI_PUBLISHED_NAME`; a clonagem está em `builder._clonar_template`.
- **Política de notificação do agendamento** → `powerbi.configurar_agendamento_com_fallback`
  e `config.REFRESH_NOTIFY_OPTION`; o uso na Fase 3 está em `pipeline.py`.
- **Mudança na regra do relatório por líder** (filtro de doações) →
  `builder.py` (`clone_and_compile_lider` e `_montar_filtro_doacao`).
- **Mudança na leitura do mapeamento líder → doação** → `datasources.py`
  (`carregar_lideres_doacoes` e `_normalizar_doacao`).
- **Novo modo do pipeline** → adicione um `_preparar_<modo>()` em `pipeline.py`
  que devolve `(unidades, compilar, schedule_path, rotulo)` e ligue-o em `main`.
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
- Não utilize travessões ("—" ou "–") em textos e documentações, pois isso denuncia textos gerados por IA. Use pontuação simples (vírgulas, dois-pontos, ponto e vírgula, parênteses).
- Comentários só quando explicam um *porquê* não óbvio (ex.: por que o schema
  PBIR exige `byConnection` e não `byItemId`, ver `builder.py`). Não
  comente o que o código já deixa claro pelo nome.
- Sem abstrações novas "para o futuro". Se três funções fizerem algo
  parecido, isso não é motivo automático para criar uma classe/base; siga o
  padrão funcional já usado no pacote.
- Erros de API sempre como `errors.APIError`, nunca `Exception` genérica, para
  manter o diagnóstico estruturado (`status_code`, `headers`, `action`).
- Segredos só em `.env` (nunca hardcoded, nunca commitados). `.env` já está no
  `.gitignore`.

## Pontos de atenção herdados do código original

- `powerbi.configurar_credenciais_sharepoint` existe mas **não é chamada** no
  fluxo principal de `pipeline.py`: as credenciais das fontes são configuradas
  manualmente no Power BI Service e o refresh agendado já funciona. Mantenha a
  função e não a chame.
- `auth.get_delegated_token` **é usado** na Fase 3, só para tentar aplicar
  `notifyOption = MailOnFailure` no agendamento (ver "Notificação de falha de
  refresh" abaixo). Não use o token delegado para outra coisa sem alinhar.

### Template, nome publicado e variáveis de ambiente

- O template é descoberto por glob em `template/`: exatamente uma pasta
  `*.SemanticModel` e uma `*.Report`, com o mesmo nome-base (qualquer nome).
  A descoberta **não levanta exceção no import**: em caso de zero/vários pares,
  `BASE_SEMANTIC_MODEL`/`BASE_REPORT` ficam `None` e `config.TEMPLATE_ERRO` traz
  a mensagem, exibida na Etapa 0 (`prerequisites.py`).
- O nome dos itens publicados vem de `PBI_PUBLISHED_NAME` (padrão `Painel
  Financeiro Executivo`), **independente** do nome do template. O upload casa
  itens por `displayName` + tipo: mudar este valor cria itens novos em vez de
  atualizar os existentes. `PBI_PROJECT_NAME` foi removido.
- `builder._clonar_template` copia o template para `build/<nome publicado>.*` e
  reescreve `metadata.displayName` do `.platform`. O `byPath` do
  `definition.pbir` do Report é substituído por `byConnection` na Fase 2
  (`fix_report_cloud_reference`), então o nome da pasta do template não importa.
- Variáveis opcionais: `PBI_PUBLISHED_NAME`, `REFRESH_NOTIFY_OPTION`,
  `DELEGATED_USER`, `DELEGATED_PASSWORD`. Exemplo de `.env` no README.md.

### Notificação de falha de refresh

- `REFRESH_NOTIFY_OPTION` (padrão `MailOnFailure`; aceitos `MailOnFailure` e
  `NoNotification`, validados na Etapa 0). Service principals só suportam
  `NoNotification` no agendamento (Microsoft Learn, "Update Refresh Schedule In
  Group"), que também exige que o chamador seja o dono do dataset.
- `powerbi.configurar_agendamento_com_fallback`: com `MailOnFailure`, tenta o
  token delegado; qualquer falha (token, 401, 403, dono diferente) gera aviso e
  refaz com `NoNotification` via SPN. **Nunca deixe um dataset sem agendamento
  por causa de notificação.** Como o SPN é o dono (TakeOver), é esperado que o
  fallback ocorra; isso **não foi validado contra o serviço real**.
- `disparar_refresh` continua com `NoNotification`: a documentação do endpoint
  diz que `notifyOption` não se aplica a operações com service principal.
- O `notifyOption` efetivamente aplicado e o aviso saem por unidade em
  `fase3[]` do log JSON, mais `notify_option_aplicado` e `avisos` no topo.

### Comuns aos dois modos

- Toda a entrada fica centralizada em `data/dados_entrada.xlsx` (nunca versionada
  no git, pois todo o conteúdo da pasta `data/` é ignorado).
- Cada modo usa suas abas correspondentes:
  gestao usa `Gestão - Áreas` + `Gestão - Agendamento`; lideres usa
  `Líderes - Doações` + `Líderes - Agendamento`. `carregar_schedule(target)`
  aceita o nome da aba ou caminho de arquivo e aceita coluna `gestor` ou `lider`.
- Os dois modos publicam no **mesmo** `WORKSPACE_ID`. Não há colisão porque os
  nomes de item diferem (`... - DAF` vs `... - Fabiana Cunha`). Rodar os dois
  cria os dois conjuntos de painéis lado a lado no workspace.
- Só `pipeline._preparar_gestao`/`_preparar_lideres` conhecem a especificidade do
  modo; o resto de `main(mode)` é genérico (itera `unidades`, chama `compilar`).
- `datasources.gerar_sql_user_dashboards(mode)` grava em tabelas diferentes no
  backend (Lovable Cloud) conforme o modo: chama `public.upsert_user_dashboard_gestao`
  ou `public.upsert_user_dashboard_lideres`, gravando em `user_dashboards_gestao`
  ou `user_dashboards_lideres` respectivamente (tabelas e funções espelhadas,
  mesma estrutura). `mode` é obrigatório aqui e a função levanta exceção se não
  for `"gestao"` ou `"lideres"`; não existe mais uma função/tabela genérica
  `upsert_user_dashboard`/`user_dashboards` sem sufixo.
- A origem dos logins é a aba de usuários da planilha única (`config.USER_DASHBOARDS_ABAS`:
  `Gestão - Usuários` ou `Líderes - Usuários` em `data/dados_entrada.xlsx`).
  Só as colunas `usuario`, `senha` e `url_painel` são lidas; as demais (identificação,
  fórmulas) são ignoradas e linhas incompletas são descartadas. O arquivo contém
  senhas em texto plano e a pasta `data/` inteira está no `.gitignore` (`data/*`);
  **nunca** o adicione ao git.

### Modo gestão (RESPONSAVEL)

- O consolidado `"GFP e KFW"` é um caso especial em `builder.clone_and_compile_gestao`
  e em `pipeline._identificar_gestores`: agrupa `GFP` com todos os gestores cujo
  nome começa com `KFW`. Qualquer mudança na regra precisa refletir nos dois lugares.
- A aba `Gestão - Áreas` ignora linhas onde `RESPONSAVEL == SUPERINTENDÊNCIA`
  (filtro intencional). Não há mais tratamento especial para a `GRI` (nem para a
  superintendência `SG`): qualquer gestão, inclusive `GRI`, que ainda apareça nas
  planilhas é um painel comum, filtrado só pelo próprio `RESPONSAVEL`.
- `clone_and_compile_gestao` **substitui** todo o `filterConfig` do report por um
  filtro `dGestão.RESPONSAVEL IN (responsáveis da gestão)` montado em
  `_montar_filtro_responsavel`; não depende de placeholder no template (antes
  dependia, e apagar o filtro no template publicava painéis sem filtro).

### Modo líderes (DOAÇÃO)

- `clone_and_compile_lider` **substitui** todo o `filterConfig` do report por um
  filtro `dDoação.DOAÇÃO IN (doações do líder)`; não depende de placeholder.
- Os nomes de doação do mapeamento precisam casar com a coluna `dDoação.DOAÇÃO`
  do modelo, normalizada com `Text.Upper(Text.Trim(Text.Clean(...)))`.
  `datasources._normalizar_doacao` replica essa regra; painel de líder vazio é
  quase sempre nome de doação digitado diferente do modelo.
- Uma mesma doação pode aparecer para mais de um líder (aparece no painel de
  cada um). Intencional, sem restrição de unicidade.
- A aba `Líderes - Doações` tem **uma linha por líder**; a coluna `doacao` traz as
  doações separadas por vírgula (a coluna `email` é só referência, não é lida
  pelo pipeline).
- Acesso irrestrito (ex.: superintendentes) **não entra** em `Líderes - Doações`:
  usa o painel mestre publicado direto da pasta `template/` (sem filtro), e o
  login é compartilhado colando a mesma `url_painel` nas linhas dessas pessoas.
