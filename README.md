# Pipeline de Publicação: Painel Financeiro Executivo

Automação que clona um template Power BI (`.pbip`), gera um painel por unidade e
publica tudo no Microsoft Fabric, configurando agendamento e disparo de refresh.
Há **dois modos**, cada um com seu `.bat`:

- **Gestão** (`run_deploy_gestao.bat`): 1 painel por gestão, filtrado por
  `RESPONSAVEL` (com consolidados GFP+KFW e GRI/SG).
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
# Opcionais (fluxo delegado de credenciais SharePoint):
DELEGATED_USER=...
DELEGATED_PASSWORD=...
```

> Segredos: **não** versione o `.env` (já está no `.gitignore`). Significado de
> cada variável e regras de formato: ver [USAGE.md § 6](USAGE.md#6-configuração-do-env).

---

## Planilhas de entrada (`data/`)

| Arquivo                         | Modo    | Obrigatório | Função                                                             |
| ------------------------------- | ------- | :---------: | ----------------------------------------------------------------- |
| `gestao_areas.xlsx`             | gestão  |     Sim     | Lista de gestões (`RESPONSAVEL`, `SUPERINTENDÊNCIA`).              |
| `refresh_schedule.xlsx`         | gestão  |     Sim     | Horários de refresh por gestão (`gestor`, `horarios`).            |
| `lideres_projeto.xlsx`          | líderes |     Sim     | Mapeamento líder -> doações (`lider`, `email`, `doacao`).          |
| `refresh_schedule_lideres.xlsx` | líderes |     Sim     | Horários de refresh por líder (`lider`, `horarios`).              |
| `user_dashboards.xlsx`          | ambos   |     Não     | Gera `sql/carga_user_dashboards_{modo}.sql` (usuario, senha, URL). |

> Cada modo só exige as planilhas do seu par. Colunas obrigatórias, exemplos e
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

A lógica é um pacote modular. Cada `.bat` chama `pbi_deploy/main.py` (via
`python -m pbi_deploy.main <gestao|lideres>`), que apenas delega para o
orquestrador. Cada módulo tem uma responsabilidade única, um desenho pensado
para manutenção, inclusive por agentes de IA. Detalhes de convenções para
agentes estão em [AGENTS.md](AGENTS.md).

```
run_deploy_gestao.bat     Entrada do usuário final (modo gestão).
run_deploy_lideres.bat    Entrada do usuário final (modo líderes).

pbi_deploy/
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
python -m pbi_deploy.main gestao
python -m pbi_deploy.main lideres
```

> Sem argumento (ou com um modo inválido), o pipeline só imprime o uso e sai
> com código 2, sem tocar a API.

## Códigos de saída

| Código | Significado                                        |
| :----: | -------------------------------------------------- |
| `0`    | Sucesso (todas as fases sem falha).                |
| `1`    | Concluído com falhas em alguma fase.               |
| `2`    | Erro fatal não tratado ou modo inválido/ausente.   |
| `130`  | Interrompido pelo usuário (Ctrl+C).                |
