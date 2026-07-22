# AGENTS.md: Guia para agentes de IA

Este arquivo é a fonte de verdade para qualquer agente de IA (Claude, Copilot,
Cursor etc.) que for editar este repositório. Leia antes de propor mudanças.

## O que é este projeto

Pipeline de publicação Power BI / Microsoft Fabric. Clona um template `.pbip`,
gera um modelo semântico + relatório por unidade, publica no Fabric e configura
agendamento/refresh. Há **dois modos**, cada um com seu `.bat`:

- **gestao** (`run_deploy_gestao.bat`): 1 painel por gestão, filtro
  `dGestão.RESPONSAVEL` (com casos especiais GFP+KFW e GRI/SG). Fonte:
  `data/gestao_areas.xlsx`.
- **lideres** (`run_deploy_lideres.bat`): 1 painel por líder de projeto, filtro
  `dDoação.DOAÇÃO` com as doações daquele líder. Fonte: `data/lideres_projeto.xlsx`.

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

Isso garante sintaxe e imports corretos sem tocar a API real. Não existe
suíte de testes automatizados neste projeto. Não invente uma sem alinhar
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
├── builder.py            Clona template -> build/, injeta filtro (gestão ou líder), fixa referência do dataset.
├── datasources.py        Lê planilhas (líderes/doações, schedule) e gera sql/carga_user_dashboards_<modo>.sql.
├── prerequisites.py      Etapa 0: valida .env, templates, planilhas (por modo), cria pastas.
├── runner.py             executar_fase(): loop genérico com progress bar + tabela + log por item.
└── pipeline.py           Orquestra as fases em main(mode)/run(mode); conhece a ordem completa e os dois modos.
```

Regra de dependência: `config`, `console` e `errors` são a camada base e
**nunca** importam outro módulo do pacote, o que evita ciclos. Todo o resto pode
importar a camada base e os módulos de domínio (`fabric`, `powerbi`,
`builder`, `datasources`), mas só `pipeline.py` conhece a sequência completa
das fases.

## Onde alterar o quê

- **Nova chamada à Fabric Items API** → `fabric.py`.
- **Nova chamada à Power BI REST API** (datasets, refresh, gateways) → `powerbi.py`.
- **Mudança na regra do relatório por gestão** (filtro RESPONSAVEL, casos GFP+KFW
  e GRI/SG) → `builder.py` (`clone_and_compile_gestao`, `_injetar_filtro_pessoal_gri`)
  e `pipeline._identificar_gestores`.
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

- `auth.get_delegated_token` e `powerbi.configurar_credenciais_sharepoint`
  existem mas **não são chamados** no fluxo principal de `pipeline.py` (a
  configuração de credenciais SharePoint é feita fora deste script hoje). Não
  remova sem confirmar com o usuário, pois pode ser um próximo passo planejado.

### Comuns aos dois modos

- Cada modo tem seu par (planilha de entrada + planilha de agendamento):
  gestao usa `gestao_areas.xlsx` + `refresh_schedule.xlsx`; lideres usa
  `lideres_projeto.xlsx` + `refresh_schedule_lideres.xlsx`. `carregar_schedule(path)`
  recebe o caminho por parâmetro e aceita coluna `gestor` ou `lider`.
- Os dois modos publicam no **mesmo** `WORKSPACE_ID`. Não há colisão porque os
  nomes de item diferem (`... - GRI` vs `... - Fabiana Cunha`). Rodar os dois
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

### Modo gestão (RESPONSAVEL)

- O consolidado `"GFP e KFW"` é um caso especial em `builder.clone_and_compile_gestao`
  e em `pipeline._identificar_gestores`: agrupa `GFP` com todos os gestores cujo
  nome começa com `KFW`. Qualquer mudança na regra precisa refletir nos dois lugares.
- O painel da `GRI` inclui no filtro report-level todos os `RESPONSAVEL` cuja
  `SUPERINTENDÊNCIA == 'SG'` (`GRI`, `PDI`, `PPI`, `SG`), lidos da planilha; e a
  página `Pessoal` recebe um filtro page-level `RESPONSAVEL = 'GRI'`
  (`_injetar_filtro_pessoal_gri`), mantendo os dados de RH só da própria GRI.
- `gestao_areas.xlsx` ignora linhas onde `RESPONSAVEL == SUPERINTENDÊNCIA`
  (filtro intencional). `SG` é suprimida como painel individual, mas seus dados
  aparecem no painel consolidado da `GRI`.
- O modo gestão depende de o template ter um filtro report-level placeholder em
  `dGestão.RESPONSAVEL` (o builder localiza esse filtro e injeta os valores).

### Modo líderes (DOAÇÃO)

- `clone_and_compile_lider` **substitui** todo o `filterConfig` do report por um
  filtro `dDoação.DOAÇÃO IN (doações do líder)`; não depende de placeholder.
- Os nomes de doação do mapeamento precisam casar com a coluna `dDoação.DOAÇÃO`
  do modelo, normalizada com `Text.Upper(Text.Trim(Text.Clean(...)))`.
  `datasources._normalizar_doacao` replica essa regra; painel de líder vazio é
  quase sempre nome de doação digitado diferente do modelo.
- Uma mesma doação pode aparecer para mais de um líder (aparece no painel de
  cada um). Intencional, sem restrição de unicidade.
- `lideres_projeto.xlsx` tem **uma linha por líder**; a coluna `doacao` traz as
  doações separadas por vírgula (a coluna `email` é só referência, não é lida
  pelo pipeline).
- Acesso irrestrito (ex.: superintendentes) **não entra** em `lideres_projeto.xlsx`:
  usa o painel mestre publicado direto da pasta `template/` (sem filtro), e o
  login é compartilhado em `user_dashboards.xlsx` colando a mesma `url_painel`.
