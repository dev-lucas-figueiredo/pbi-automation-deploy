# Guia de Uso: Pipeline de Publicação Power BI

Guia completo e passo a passo de como preparar os arquivos e executar o
pipeline. Para uma visão geral do projeto e da arquitetura, consulte o
[README.md](README.md).

---

## Índice

1. [Visão geral do fluxo](#1-visão-geral-do-fluxo)
2. [Primeiros passos após o download](#2-primeiros-passos-após-o-download)
3. [Estrutura de pastas esperada](#3-estrutura-de-pastas-esperada)
4. [Preparação do template Power BI](#4-preparação-do-template-power-bi)
5. [Planilhas de entrada (pasta `data/`)](#5-planilhas-de-entrada-pasta-data)
   - 5.1 [`gestao_areas.xlsx`](#51-gestao_areasxlsx)
   - 5.2 [`refresh_schedule.xlsx`](#52-refresh_schedulexlsx)
   - 5.3 [`user_dashboards.xlsx`](#53-user_dashboardsxlsx)
6. [Configuração do `.env`](#6-configuração-do-env)
7. [Execução do pipeline](#7-execução-do-pipeline)
8. [O que acontece em cada etapa](#8-o-que-acontece-em-cada-etapa)
9. [Saídas geradas](#9-saídas-geradas)
10. [Perguntas frequentes](#10-perguntas-frequentes)

---

## 1. Visão geral do fluxo

```
                   ┌────────────────────┐
                   │  Usuário prepara:  │
                   │  • Template .pbip  │
                   │  • Planilhas Excel │
                   │  • Arquivo .env    │
                   └────────┬───────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │  run_deploy.bat    │
                   │  (duplo clique)    │
                   └────────┬───────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                  ▼
   ┌─────────────┐  ┌─────────────┐   ┌─────────────┐
   │ Fase 1      │  │ Fase 2      │   │ Fase 3      │
   │ Modelos     │  │ Relatórios  │   │ Pós-deploy  │
   │ Semânticos  │  │ Vinculados  │   │ TakeOver +  │
   │ (1 por      │  │ (1 por      │   │ Agendamento │
   │  gestão)    │  │  gestão)    │   │ + Refresh   │
   └─────────────┘  └─────────────┘   └─────────────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ▼
                   ┌────────────────────┐
                   │  Saídas:           │
                   │  • build/          │
                   │  • logs/           │
                   │  • sql/            │
                   └────────────────────┘
```

O pipeline lê o template Power BI, clona uma cópia por gestão (injetando o
filtro de `RESPONSAVEL`), publica cada modelo semântico e relatório no
Microsoft Fabric, e por fim configura agendamento de refresh e dispara uma
atualização inicial.

---

## 2. Primeiros passos após o download

Ao baixar o repositório, alguns arquivos **não estão incluídos** no download
por questões de segurança e privacidade. Antes de executar o pipeline pela
primeira vez, você precisa adicioná-los manualmente:

| Arquivo / Pasta             | Onde colocar         | Como obter                                                                    |
| --------------------------- | -------------------- | ----------------------------------------------------------------------------- |
| `.env`                      | Raiz do projeto      | Solicite ao administrador do projeto. Contém credenciais Azure e chaves.       |
| Template Power BI (`.pbip`) | Pasta `template/`    | Salve o relatório-mestre no formato `.pbip` dentro de `template/` (ver seção 4). |
| `user_dashboards.xlsx`      | Pasta `data/`        | Solicite ao administrador. Opcional, sendo necessário apenas para geração de SQL.  |

Os demais arquivos (código, planilhas `gestao_areas.xlsx` e
`refresh_schedule.xlsx`, ambiente Python `env/`, etc.) **já vêm incluídos** no
download e estão prontos para uso.

---

## 3. Estrutura de pastas esperada

Após adicionar os arquivos faltantes, a raiz do projeto deve ficar assim:

```
pbi-automation-deploy/
├── .env                                 ← adicionar manualmente (ver seção 6)
├── run_deploy.bat                       ← entrada do usuário
├── requirements.txt                     ← dependências Python
│
├── data/                                ← planilhas de entrada (ver seção 5)
│   ├── gestao_areas.xlsx                   (já incluída no download)
│   ├── refresh_schedule.xlsx               (já incluída no download)
│   └── user_dashboards.xlsx                (adicionar manualmente, opcional)
│
├── template/                            ← adicionar o template Power BI (ver seção 4)
│   ├── Painel Financeiro Executivo.pbip
│   ├── Painel Financeiro Executivo.SemanticModel/
│   └── Painel Financeiro Executivo.Report/
│
├── env/                                 ← ambiente virtual Python (já incluído)
├── pbi_deploy/                          ← código do pipeline (não alterar)
│
├── build/                               ← já incluída (inicialmente vazia, recebe relatórios gerados)
├── logs/                                ← já incluída (inicialmente vazia, recebe os logs de execução)
└── sql/                                 ← já incluída (inicialmente vazia, recebe scripts SQL)
```

> As pastas `build/`, `logs/` e `sql/` já vêm incluídas na estrutura do repositório
> (inicialmente vazias). O pipeline irá salvar nelas os arquivos gerados durante a execução.

---

## 4. Preparação do template Power BI

O template é o relatório-mestre a partir do qual o pipeline gera uma cópia por
gestão. Ele deve estar salvo no **formato `.pbip`** (Power BI Project) dentro
da pasta `template/`.

### 4.1. Como salvar no formato `.pbip`

1. Abra o relatório no **Power BI Desktop**.
2. Vá em **Arquivo → Salvar como**.
3. Na janela de salvamento, altere o tipo de arquivo para
   **Power BI Project (`.pbip`)**.
4. Salve dentro da pasta `template/` do projeto com o nome
   **`Painel Financeiro Executivo`**.

Ao salvar, o Power BI Desktop cria automaticamente três itens:

| Item criado                                      | Tipo   | Descrição                                                   |
| ------------------------------------------------ | ------ | ----------------------------------------------------------- |
| `Painel Financeiro Executivo.pbip`                | Arquivo | Manifesto do projeto. Liga o relatório ao modelo semântico. |
| `Painel Financeiro Executivo.SemanticModel/`      | Pasta  | Modelo de dados (tabelas, medidas, relações) em TMDL.       |
| `Painel Financeiro Executivo.Report/`             | Pasta  | Visuais, páginas, filtros e bookmarks do relatório.         |

### 4.2. Requisitos do template

- O relatório **deve** conter um filtro de nível de relatório (report-level
  filter) na entidade `dGestão`, propriedade `RESPONSAVEL`. É esse filtro que
  o pipeline injeta para separar os dados por gestão.
- O nome do projeto deve ser exatamente **`Painel Financeiro Executivo`**
  (é o valor da constante `PBI_PROJECT_NAME` em `config.py`).
- Não renomeie as pastas `.SemanticModel` e `.Report`, pois o pipeline depende
  dessa nomenclatura para localizar os artefatos.

### 4.3. Atualizando o template

Para atualizar o template (ex.: novo visual, nova medida), basta:

1. Abrir o `.pbip` no Power BI Desktop.
2. Fazer as alterações desejadas.
3. Salvar normalmente (**Ctrl+S**). O Power BI sobrescreve os arquivos na
   mesma pasta `template/`.
4. Executar `run_deploy.bat` novamente. O pipeline criará ou atualizará os
   painéis publicados com base no template atualizado.

> **Importante:** Não edite manualmente os arquivos JSON dentro das pastas
> `.SemanticModel/` e `.Report/` a menos que saiba exatamente o que está
> fazendo. Use sempre o Power BI Desktop para alterações.

---

## 5. Planilhas de entrada (pasta `data/`)

O pipeline lê três planilhas Excel. Todas devem ficar na pasta `data/`.

---

### 5.1. `gestao_areas.xlsx`

| Atributo       | Valor                                                              |
| -------------- | ------------------------------------------------------------------ |
| **Obrigatória** | Sim                                                                |
| **Função**     | Define a lista de gestões da FAS para os quais o pipeline criará painéis |
| **Lida por**   | `pipeline.py` (função `_identificar_gestores`)                     |

#### Colunas necessárias

| Coluna           | Tipo   | Descrição                                                                                                        |
| ---------------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| `RESPONSAVEL`    | Texto  | Nome da gestão da FAS a qual o relatório será destinado. Cada valor único gera um painel separado.                                            |
| `SUPERINTENDÊNCIA` | Texto | Superintendência à qual a gestão pertence. Linhas onde `RESPONSAVEL` é igual a `SUPERINTENDÊNCIA` são **ignoradas** (filtro intencional para evitar que superintendências apareçam como gestões individuais). |

#### Exemplo

| RESPONSAVEL | SUPERINTENDÊNCIA | ... (outras colunas) |
| ----------- | ---------------- | -------------------- |
| GESTÃO A    | SUPER X          | ...                  |
| GESTÃO B    | SUPER X          | ...                  |
| SUPER X     | SUPER X          | ← ignorado          |
| GFP         | SUPER Y          | ...                  |
| KFW 01      | SUPER Z          | ...                  |
| KFW 02      | SUPER Z          | ...                  |

#### Regra especial: consolidado GFP e KFW

O pipeline detecta automaticamente gestões cujo nome começa com `KFW`. Quando
existem gestões KFW:

- A gestão `GFP` é **removida** da lista individual.
- Um painel consolidado chamado **`GFP e KFW`** é adicionado, agrupando a `GFP` com todas as gestões `KFW*`.
- Esse painel recebe um filtro múltiplo de `RESPONSAVEL` com todos esses nomes.

#### Regra especial: painel da GRI com dados da superintendência SG

O painel da `GRI` exibe dados de **todos os responsáveis cuja `SUPERINTENDÊNCIA` é `SG`**
(`GRI`, `PDI`, `PPI` e `SG`), lidos dinamicamente da planilha. Excecao: a pagina
**Pessoal** exibe apenas os dados da propria `GRI` (filtro de pagina adicional).

- Nenhuma dessas gestoes perde seu painel individual.
- A `SG` continua suprimida como painel individual (regra `RESPONSAVEL == SUPERINTENDENCIA`),
  mas seus dados aparecem no painel da `GRI`.
- Para alterar quais gestores compoe o consolidado da GRI, edite
  `builder.clone_and_compile` (caso `elif gestao_name == "GRI"`).

---

### 5.2. `refresh_schedule.xlsx`

| Atributo       | Valor                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------- |
| **Obrigatória** | Sim                                                                                       |
| **Função**     | Define os horários de atualização automática (refresh) para o modelo semântico de cada gestão |
| **Lida por**   | `datasources.py` (função `carregar_schedule`)                                              |

#### Colunas necessárias

| Coluna     | Tipo  | Descrição                                                                                                                                      |
| ---------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `gestor`   | Texto | Nome da gestão, **exatamente como aparece** na coluna `RESPONSAVEL` de `gestao_areas.xlsx` (ou `GFP e KFW` para o consolidado).                 |
| `horarios` | Texto | Horários de refresh separados por vírgula, no formato `HH:MM`. Fuso: **SA Western Standard Time (UTC−4, Manaus)**. Se vazio, o agendamento é desativado. |

#### Exemplo

| gestor     | horarios          |
| ---------- | ----------------- |
| GESTÃO A   | 08:00,12:00,18:00 |
| GESTÃO B   | 08:00,18:00       |
| GFP e KFW  | 07:00,13:00       |
| GESTÃO C   |                   |

> **Notas:**
> - Gestões que **não aparecem** nesta planilha recebem o horário padrão
>   `08:00, 18:00`.
> - Gestões com a célula `horarios` **vazia** terão o agendamento
>   **desativado** (sem refresh automático).
> - O agendamento roda **todos os dias da semana** (domingo a sábado).

---

### 5.3. `user_dashboards.xlsx`

| Atributo       | Valor                                                                              |
| -------------- | ---------------------------------------------------------------------------------- |
| **Obrigatória** | Não                                                                                |
| **Função**     | Gera o arquivo `sql/carga_user_dashboards.sql` com comandos de upsert para um banco PostgreSQL |
| **Lida por**   | `datasources.py` (função `gerar_sql_user_dashboards`)                               |

#### Colunas necessárias

| Coluna       | Tipo  | Descrição                                                                                    |
| ------------ | ----- | -------------------------------------------------------------------------------------------- |
| `usuario`    | Texto | Nome de usuário para acesso ao dashboard (ex.: seu.nome@fas-amazonia.org).                     |
| `senha`      | Texto | Senha do usuário.                                                                            |
| `url_painel` | Texto | URL do painel publicado no Power BI. Será criptografada no SQL gerado usando `URL_ENCRYPTION_KEY`. |

#### Exemplo

| usuario      | senha    | url_painel                                             |
| ------------ | -------- | ------------------------------------------------------ |
| joao.silva@fas-amazonia.org   | S3nh@123 | https://app.powerbi.com/view?r=eyJ...                  |
| maria.souza@fas-amazonia.org  | M@ri4!   | https://app.powerbi.com/view?r=abc...                  |

#### O que o SQL gerado faz

O arquivo `sql/carga_user_dashboards.sql` produzido contém:

1. `SET app.url_key`, que define a chave de criptografia da sessão (valor de
   `URL_ENCRYPTION_KEY` no `.env`).
2. Uma chamada `SELECT public.upsert_user_dashboard(...)` por linha da
   planilha, criando ou atualizando o registro do usuário no banco.
3. Tudo envolto em uma transação `BEGIN ... COMMIT`.

> **Nota:** Esta planilha **não vem incluída** no download do repositório.
> Se não existir na pasta `data/`, o pipeline simplesmente pula a geração de
> SQL. Nenhum erro é gerado.

---

## 6. Configuração do `.env`

O arquivo `.env` **não vem incluído** no download do repositório por conter
credenciais sensíveis. Solicite-o ao administrador do projeto e coloque-o na
**raiz do projeto** (ao lado de `run_deploy.bat`).

Este arquivo contém os segredos de autenticação e **nunca deve ser
compartilhado ou versionado** (já está no `.gitignore`).

### Variáveis obrigatórias

| Variável            | Descrição                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `TENANT_ID`         | ID do tenant Azure AD (Microsoft Entra ID) onde o Service Principal está registrado.                                                  |
| `CLIENT_ID`         | ID de aplicação (Application ID) do Service Principal registrado no Azure AD.                                                         |
| `CLIENT_SECRET`     | Segredo (client secret) do Service Principal. Gerado na seção *Certificates & secrets* do registro de app no portal Azure.            |
| `WORKSPACE_ID`      | ID do workspace no Microsoft Fabric / Power BI Service onde os painéis serão publicados. Pode ser encontrado na URL do workspace.      |
| `URL_ENCRYPTION_KEY`| Chave usada para criptografar as URLs dos painéis no SQL gerado por `user_dashboards.xlsx`. Deve ser a mesma chave usada no banco de dados. |

### Variáveis opcionais

| Variável             | Descrição                                                                                                              |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `DELEGATED_USER`     | E-mail da conta de serviço para fluxo delegado (ROPC). Necessário apenas para configuração de credenciais SharePoint.   |
| `DELEGATED_PASSWORD` | Senha da conta de serviço acima.                                                                                       |

> As variáveis delegadas (`DELEGATED_USER`/`DELEGATED_PASSWORD`) **não são
> usadas** no fluxo principal hoje. Existem para um futuro fluxo de
> configuração automática de credenciais SharePoint.

### Formato do arquivo

```env
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CLIENT_SECRET=sua-chave-secreta-aqui
WORKSPACE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
URL_ENCRYPTION_KEY=sua-chave-de-criptografia-aqui
```

> Sem aspas, sem espaços ao redor do `=`, uma variável por linha.

---

## 7. Execução do pipeline

Após preparar o template, as planilhas e o `.env`, basta dar **duplo clique**
em **`run_deploy.bat`**.

> **Não é necessário instalar Python nem criar ambiente virtual.** A pasta
> `env/` já vem incluída no projeto com o interpretador e todas as
> dependências prontas para uso.

O que o `run_deploy.bat` faz automaticamente:

1. Verifica se `env/`, `.env` e `pbi_deploy/main.py` existem.
2. Ativa o ambiente virtual já incluído na pasta `env/`.
3. Verifica se a biblioteca `rich` está instalada (instala se necessário).
4. Instala/atualiza as demais dependências de `requirements.txt`.
5. Executa o pipeline Python (`python -m pbi_deploy.main`).
6. Exibe o resultado final (**SUCESSO**, **PARCIAL** ou **FALHA**) e aguarda
   `Enter`.

> **Não feche a janela** enquanto o pipeline estiver rodando. O progresso é
> exibido no terminal em tempo real com barras de progresso e tabelas.

---

## 8. O que acontece em cada etapa

| Etapa   | Nome                   | O que faz                                                                                          |
| ------- | ---------------------- | -------------------------------------------------------------------------------------------------- |
| Etapa 0 | Pré-requisitos         | Valida que todas as variáveis do `.env`, templates e planilhas estão presentes e garante que as pastas `build/`, `logs/` e `sql/` existam. |
| Etapa 1 | Autenticação           | Obtém token OAuth2 do Azure AD usando o Service Principal (Client Credentials).                     |
| Etapa 2 | Inspeção do workspace  | Lista todos os itens existentes no workspace Fabric para decidir se criará ou atualizará cada um.   |
| Fase 1  | Modelos semânticos     | Clona o template, compila um modelo semântico por gestão e faz upload via Fabric Items API.         |
| Fase 2  | Relatórios vinculados  | Ajusta a referência ao modelo semântico publicado e faz upload do relatório via Fabric Items API.   |
| Fase 3  | Pós-deploy             | Executa TakeOver (posse do dataset pelo SPN), configura agendamento de refresh e dispara refresh inicial. |
| Final   | Resumo e SQL           | Exibe tabela com resumo executivo, salva log JSON em `logs/` e gera SQL em `sql/` (se `user_dashboards.xlsx` existir). |

---

## 9. Saídas geradas

Após a execução, o pipeline produz:

| Pasta    | Conteúdo                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------- |
| `build/` | Artefatos compilados (uma pasta `.SemanticModel` e uma `.Report` por gestão). Pode ser ignorada pelo usuário, pois é intermediária. |
| `logs/`  | Arquivo JSON por execução (`deploy_YYYYMMDD_HHMMSS.json`) com log detalhado de cada fase, tempos e erros. |
| `sql/`   | `carga_user_dashboards.sql`: script SQL para carga de usuários no banco de dados (gerado apenas se `user_dashboards.xlsx` existir). |

---

## 10. Perguntas frequentes

### O pipeline altera meu template original?

**Não.** O pipeline copia o template para `build/` e faz as alterações na
cópia. A pasta `template/` permanece intacta.

### Posso rodar o pipeline várias vezes?

**Sim.** Se os itens já existirem no workspace, o pipeline os **atualiza** em
vez de criar duplicatas. É seguro re-executar.

### O pipeline publica em produção?

**Sim.** O deploy é feito diretamente no workspace configurado em
`WORKSPACE_ID`. Certifique-se de que é o workspace correto antes de executar.

### Como adicionar uma nova gestão?

1. Adicione uma linha na planilha `data/gestao_areas.xlsx` com o nome da gestão na
   coluna `RESPONSAVEL`.
2. Opcionalmente, adicione a gestão em `data/refresh_schedule.xlsx` com os horários
   desejados (se não adicionar, usará `08:00, 18:00` como padrão).
3. Execute `run_deploy.bat`.

### Como remover uma gestão do pipeline?

Remova a gestão de `data/gestao_areas.xlsx`. Na próxima execução, o pipeline
simplesmente não processará aquela gestão. **O painel já publicado no workspace
não é excluído automaticamente**; você precisará removê-lo manualmente pelo
portal do Fabric/Power BI.

### O que significa "GFP e KFW" no consolidado?

Quando há gestões cujo nome começa com `KFW` na planilha, o pipeline
automaticamente cria um painel consolidado chamado `GFP e KFW`, que filtra os
dados por `GFP` + todas as gestões `KFW*`. Nesse caso, a gestão `GFP` não
recebe painel individual, apenas o consolidado.

### O que é o agendamento de refresh?

Após publicar os modelos, o pipeline configura a atualização automática dos
dados no Power BI Service. Os horários vêm de `refresh_schedule.xlsx` e o fuso
horário é **SA Western Standard Time (UTC−4, horário de Manaus)**.

### Onde encontro os logs de erro?

Na pasta `logs/`, em um arquivo JSON nomeado com a data e hora da execução. O
arquivo contém o resultado detalhado de cada fase (gestor, status, tempo, erro).
