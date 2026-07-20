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
   - 5.1 [`lideres_projeto.xlsx`](#51-lideres_projetoxlsx)
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
   │  líder)     │  │  líder)     │   │ + Refresh   │
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

O pipeline lê o template Power BI, clona uma cópia por líder de projeto
(injetando o filtro com as doações daquele líder na entidade `dDoação`),
publica cada modelo semântico e relatório no Microsoft Fabric, e por fim
configura agendamento de refresh e dispara uma atualização inicial.

---

## 2. Primeiros passos após o download

Ao baixar o repositório, alguns arquivos **não estão incluídos** no download
por questões de segurança e privacidade. Antes de executar o pipeline pela
primeira vez, você precisa adicioná-los manualmente:

| Arquivo / Pasta             | Onde colocar         | Como obter                                                                    |
| --------------------------- | -------------------- | ----------------------------------------------------------------------------- |
| `.env`                      | Raiz do projeto      | Solicite ao administrador do projeto. Contém credenciais Azure e chaves.       |
| Template Power BI (`.pbip`) | Pasta `template/`    | Salve o relatório-mestre no formato `.pbip` dentro de `template/` (ver seção 4). |
| `lideres_projeto.xlsx`      | Pasta `data/`        | Monte o mapeamento líder -> doação (ver seção 5.1). Define quais painéis serão gerados. |
| `user_dashboards.xlsx`      | Pasta `data/`        | Solicite ao administrador. Opcional, sendo necessário apenas para geração de SQL.  |

Os demais arquivos (código, planilha `refresh_schedule.xlsx`, ambiente Python
`env/`, etc.) **já vêm incluídos** no download e estão prontos para uso.

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
│   ├── lideres_projeto.xlsx                (adicionar manualmente, ver seção 5.1)
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

- O modelo semântico **deve** conter a tabela `dDoação` com a coluna `DOAÇÃO`.
  É nessa entidade que o pipeline injeta o filtro report-level com as doações
  de cada líder. O pipeline substitui todo o filtro de nível de relatório na
  cópia gerada, então não é preciso deixar nenhum filtro placeholder no template.
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

### 5.1. `lideres_projeto.xlsx`

| Atributo        | Valor                                                                    |
| --------------- | ------------------------------------------------------------------------ |
| **Obrigatória** | Sim                                                                      |
| **Função**      | Mapeia cada líder de projeto às doações que ele lidera. Cada líder vira um painel. |
| **Lida por**    | `datasources.py` (função `carregar_lideres_doacoes`)                     |

#### Colunas necessárias

| Coluna    | Tipo  | Descrição                                                                                              |
| --------- | ----- | ----------------------------------------------------------------------------------------------------- |
| `lider`   | Texto | Nome do líder de projeto. **Uma linha por líder** (não repita o líder em várias linhas). Cada líder distinto gera um painel separado (o nome vira o sufixo do painel). |
| `doacao`  | Texto | Todas as doações lideradas por esse líder, **separadas por vírgula**, na mesma célula.                 |

#### Exemplo

| lider             | doacao                                                        |
| ------------------ | -------------------------------------------------------------- |
| Fabiana Cunha       | ARTERY PRODUCOES_2025_01, SWAROVSKI_2025_01, FUMCAD BERURI      |
| Gabriela Sampaio    | ABDI_2025_01, AMAZONIA ANDES 2025_01                            |

#### Regras e observações

- Linhas com `lider` **ou** `doacao` em branco são **ignoradas**.
- Doações repetidas na mesma célula (mesmo líder) são deduplicadas automaticamente.
- Uma mesma doação pode aparecer para **mais de um líder** (ela entra no painel
  de cada um). Não há restrição de unicidade.
- Os nomes em `doacao` precisam corresponder aos valores da coluna `DOAÇÃO` do
  modelo. O pipeline normaliza automaticamente (maiúsculas, sem espaços nas
  pontas, sem caracteres de controle), mas diferenças de digitação no meio do
  texto **não** são corrigidas. Sintoma típico de nome errado: o painel do líder
  abre **vazio**. Confira os nomes de doação exatamente como aparecem no relatório.

#### Acesso irrestrito (ex.: superintendentes)

Pessoas que precisam ver **todas** as doações sem filtro (ex.: superintendentes)
**não entram** em `lideres_projeto.xlsx`. Elas usam o painel mestre publicado
diretamente a partir da pasta `template/` (sem filtro de doação, gerado fora
deste pipeline), não um painel gerado por líder.

O compartilhamento acontece em `user_dashboards.xlsx` (seção 5.3): publique o
painel mestre uma vez e cole a **mesma `url_painel`** nas linhas de cada pessoa
com acesso irrestrito. Cada pessoa mantém seu próprio usuário/senha, mas todas
apontam para o mesmo painel mestre.

---

### 5.2. `refresh_schedule.xlsx`

| Atributo       | Valor                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------- |
| **Obrigatória** | Sim                                                                                       |
| **Função**     | Define os horários de atualização automática (refresh) para o modelo semântico de cada líder |
| **Lida por**   | `datasources.py` (função `carregar_schedule`)                                              |

#### Colunas necessárias

| Coluna     | Tipo  | Descrição                                                                                                                                      |
| ---------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `lider`    | Texto | Nome do líder, **exatamente como aparece** na coluna `lider` de `lideres_projeto.xlsx`.                                                         |
| `horarios` | Texto | Horários de refresh separados por vírgula, no formato `HH:MM`. Fuso: **SA Western Standard Time (UTC−4, Manaus)**. Se vazio, o agendamento é desativado. |

#### Exemplo

| lider            | horarios          |
| ---------------- | ----------------- |
| Fabiana Cunha    | 08:00,12:00,18:00 |
| Gabriela Sampaio | 08:00,18:00       |
| Rosa Anjos       | 07:00,13:00       |
| Wildney Mourão   |                   |

> **Notas:**
> - Líderes que **não aparecem** nesta planilha recebem o horário padrão
>   `08:00, 18:00`.
> - Líderes com a célula `horarios` **vazia** terão o agendamento
>   **desativado** (sem refresh automático).
> - O agendamento roda **todos os dias da semana** (domingo a sábado).
> - Para compatibilidade, o pipeline ainda aceita a coluna antiga `gestor` caso
>   `lider` não exista na planilha.

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
| Fase 1  | Modelos semânticos     | Clona o template, compila um modelo semântico por líder e faz upload via Fabric Items API.           |
| Fase 2  | Relatórios vinculados  | Ajusta a referência ao modelo semântico publicado e faz upload do relatório via Fabric Items API.   |
| Fase 3  | Pós-deploy             | Executa TakeOver (posse do dataset pelo SPN), configura agendamento de refresh e dispara refresh inicial. |
| Final   | Resumo e SQL           | Exibe tabela com resumo executivo, salva log JSON em `logs/` e gera SQL em `sql/` (se `user_dashboards.xlsx` existir). |

---

## 9. Saídas geradas

Após a execução, o pipeline produz:

| Pasta    | Conteúdo                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------- |
| `build/` | Artefatos compilados (uma pasta `.SemanticModel` e uma `.Report` por líder). Pode ser ignorada pelo usuário, pois é intermediária. |
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

### Como adicionar um novo líder?

1. Adicione uma linha em `data/lideres_projeto.xlsx` com o nome do líder na
   coluna `lider` e todas as doações dele, separadas por vírgula, na coluna
   `doacao`.
2. Opcionalmente, adicione o líder em `data/refresh_schedule.xlsx` com os horários
   desejados (se não adicionar, usará `08:00, 18:00` como padrão).
3. Execute `run_deploy.bat`.

### Como remover um líder do pipeline?

Remova as linhas daquele líder em `data/lideres_projeto.xlsx`. Na próxima
execução, o pipeline simplesmente não processará aquele líder. **O painel já
publicado no workspace não é excluído automaticamente**; você precisará removê-lo
manualmente pelo portal do Fabric/Power BI.

### O painel de um líder abriu vazio. O que houve?

Quase sempre é um nome de doação em `lideres_projeto.xlsx` que não corresponde
exatamente à coluna `DOAÇÃO` do modelo. Confira o nome da doação como ele aparece
no relatório e ajuste a planilha (o pipeline normaliza maiúsculas e espaços das
pontas, mas não corrige diferenças de digitação no meio do texto).

### O que é o agendamento de refresh?

Após publicar os modelos, o pipeline configura a atualização automática dos
dados no Power BI Service. Os horários vêm de `refresh_schedule.xlsx` e o fuso
horário é **SA Western Standard Time (UTC−4, horário de Manaus)**.

### Onde encontro os logs de erro?

Na pasta `logs/`, em um arquivo JSON nomeado com a data e hora da execução. O
arquivo contém o resultado detalhado de cada fase (gestor, status, tempo, erro).
