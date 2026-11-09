# Pipeline de Publicação: Painel Financeiro Executivo

Automação que clona um template Power BI (`.pbip`), gera um painel por unidade e
publica tudo no Microsoft Fabric, configurando agendamento e disparo de refresh.
Há **dois modos**, cada um com seu `.bat`:

- **Gestão** (`run_deploy_gestao.bat`): 1 painel por gestão, filtrado por
  `RESPONSAVEL` (com o consolidado GFP+KFW).
- **Líderes** (`run_deploy_lideres.bat`): 1 painel por líder de projeto, filtrado
  pelas doações que aquele líder lidera.

> **Novo aqui?** Leia o [USAGE.md](USAGE.md), um guia completo de como preparar
> os arquivos e executar o pipeline.

---

## Para o usuário final

Dê **duplo clique** no `.bat` do modo desejado: **`run_deploy_gestao.bat`** (por
gestão) ou **`run_deploy_lideres.bat`** (por líder de projeto). Os dois podem ser
executados no mesmo workspace (os nomes dos painéis não colidem). Detalhes de
preparação de arquivos, planilhas e template estão no [USAGE.md](USAGE.md).

---

## Configuração (`.env`)

```env
TENANT_ID=...
CLIENT_ID=...
CLIENT_SECRET=...
WORKSPACE_ID=...
URL_ENCRYPTION_KEY=...
# Opcionais:
REFRESH_NOTIFY_OPTION=MailOnFailure              # ou NoNotification (padrão: MailOnFailure)
DELEGATED_USER=...       # conta usada só para tentar MailOnFailure no agendamento
DELEGATED_PASSWORD=...
```

- **Template:** qualquer nome. O pipeline localiza a única pasta `*.SemanticModel`
  e a única `*.Report` em `template/`. O nome dos itens publicados adota dinamicamente
  o próprio nome do template + ` - <unidade>` (sem necessidade de variável no `.env`).
  Alterar o nome do template cria itens novos no workspace (o upload casa por nome).
- **Notificação de falha de refresh:** com `MailOnFailure` o agendamento é tentado
  com a conta delegada; se não for possível (ex.: o dataset pertence ao SPN), o
  pipeline avisa e mantém o agendamento com `NoNotification`. Ver
  [USAGE.md § 10](USAGE.md#10-passo-obrigatório-após-a-execução-assumir-controle-dos-datasets).
- **Credenciais das fontes** (SharePoint etc.) são configuradas manualmente no
  Power BI Service; o pipeline não as altera.

> Segredos: **não** versione o `.env` (já está no `.gitignore`). Significado de
> cada variável e regras de formato: ver [USAGE.md § 6](USAGE.md#6-configuração-do-env).

---

## Planilha única de entrada (`data/dados_entrada.xlsx`)

Toda a configuração de entrada do pipeline fica centralizada em um único arquivo: **`data/dados_entrada.xlsx`** (ignorado pelo git, pois contém credenciais e dados operacionais).

| Aba                     | Modo    | Obrigatório | Função                                                             |
| ----------------------- | ------- | :---------: | ----------------------------------------------------------------- |
| `Gestão - Áreas`        | gestão  |     Sim     | Lista de gestões (`GestaoKey`, `RESPONSAVEL`, `SUPERINTENDÊNCIA`).  |
| `Gestão - Agendamento`  | gestão  |     Sim     | Horários de refresh por gestão (`gestor`, `horarios`).            |
| `Gestão - Usuários`     | gestão  |     Não     | Logins do Lovable para gestão. Gera `sql/carga_user_dashboards_gestao.sql`. |
| `Líderes - Doações`     | líderes |     Sim     | Mapeamento líder para doações (`lider`, `doacao`).                |
| `Líderes - Agendamento` | líderes |     Sim     | Horários de refresh por líder (`lider`, `horarios`).              |
| `Líderes - Usuários`    | líderes |     Não     | Logins do Lovable para líderes. Gera `sql/carga_user_dashboards_lideres.sql`. |

> Cada modo só exige as abas correspondentes. Colunas obrigatórias, exemplos e
> regras especiais: ver [USAGE.md § 5](USAGE.md#5-planilhas-de-entrada-pasta-data).

---

## O que o pipeline faz

1. **Etapas 0 a 2 (preparação):** valida `.env`/templates/planilhas (conforme o
   modo), autentica no Azure AD (Service Principal) e inspeciona os itens do workspace.
2. **Fase 1 (Modelos semânticos):** clona o template e publica um modelo por unidade
   (gestão ou líder).
3. **Fase 2 (Relatórios):** publica os relatórios vinculados ao modelo correspondente.
4. **Fase 3 (Pós-deploy):** TakeOver, agendamento e disparo do refresh inicial.

Saídas em `build/` (artefatos), `logs/` (JSON por execução) e `sql/`. Detalhe
fase a fase em [USAGE.md § 8](USAGE.md#8-o-que-acontece-em-cada-etapa).

---

## Arquitetura do código

A lógica é um pacote modular. Cada `.bat` chama `src/main.py` (via
`python -m src.main <gestao|lideres>`), que apenas delega para o
orquestrador. Cada módulo tem uma responsabilidade única, um desenho pensado
para manutenção, inclusive por agentes de IA. Detalhes de convenções para
agentes estão em [AGENTS.md](AGENTS.md).

```
run_deploy_gestao.bat     Entrada do usuário final (modo gestão).
run_deploy_lideres.bat    Entrada do usuário final (modo líderes).

src/
├── __init__.py           Documentação do pacote e atalho main().
├── main.py               Entrypoint fino: lê o modo do argv e delega para pipeline.run.
├── config.py             Variáveis de ambiente, caminhos e constantes.
├── console.py            Console rich compartilhado, mask() e banner().
├── errors.py             APIError e parsing seguro de respostas.
├── auth.py               Autenticação Azure AD (Service Principal e delegado).
├── fabric.py             Fabric Items API: listar, criar/atualizar, poll LRO.
├── powerbi.py            Power BI REST: TakeOver, schedule, refresh, SharePoint.
├── builder.py            Clonagem/compilação dos artefatos .pbip (por gestão ou por líder).
├── datasources.py        Leitura das planilhas e geração de SQL.
├── prerequisites.py      Validação de pré-requisitos por modo (Etapa 0).
├── runner.py             Executor genérico de uma fase (progresso + tabela).
└── pipeline.py           Orquestração das fases (main(mode) / run(mode)).

tests/                    Testes unitários (pytest; pip install -r requirements-dev.txt).
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
python -m src.main gestao
python -m src.main lideres
```

> Sem argumento (ou com um modo inválido), o pipeline só imprime o uso e sai
> com código 2, sem tocar a API.

## Testes

```bat
pip install -r requirements-dev.txt
pytest
```

Não acessam a API (HTTP simulado). Cobrem a descoberta do template, os nomes
publicados, os responsáveis por gestão e o fallback de `notifyOption`.

## Códigos de saída

| Código | Significado                                        |
| :----: | -------------------------------------------------- |
| `0`    | Sucesso (todas as fases sem falha).                |
| `1`    | Concluído com falhas em alguma fase.               |
| `2`    | Erro fatal não tratado ou modo inválido/ausente.   |
| `130`  | Interrompido pelo usuário (Ctrl+C).                |
