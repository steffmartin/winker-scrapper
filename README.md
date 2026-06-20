# Winker Scraper & Dashboard Financeiro

Este projeto consiste em uma automação robusta para extração de lançamentos, transações e anexos financeiros do portal Winker, acoplado a um Dashboard nativo para Desktop de nível premium baseado no template **Sakai PrimeNG** (Angular v21 + PrimeNG v21 + Tailwind CSS v4).

---

## 📋 Pré-requisitos

Para rodar e compilar este projeto em sua máquina local, você precisará de:

1. **Python 3.10+**: Com as dependências do projeto instaladas (`playwright`, `python-dotenv`, `pywebview`).
2. **Node.js (v18+)**: Necessário apenas para realizar a compilação inicial de produção do frontend em Angular.

---

## ⚡ Instalação e Primeira Execução

Para facilitar o uso sem a necessidade de rodar comandos complexos no console do terminal, criamos atalhos prontos na raiz do projeto.

### Passo 1: Configurar Credenciais
Crie ou edite o arquivo `.env` na raiz do projeto contendo suas credenciais de login no portal Winker:
```env
WINKER_USER=seu_email@provedor.com
WINKER_PASSWORD=sua_senha
WINKER_CONDO=nome_ou_id_do_condominio
```

### Passo 2: Primeira Execução e Compilação Automática
Se você acabou de clonar este repositório do zero, a pasta de arquivos estáticos `compilados/` não estará presente.
* Basta dar um duplo clique no atalho [**`Visualizar_Dashboard.lnk`**](file:///D:/projects/winker/Visualizar_Dashboard.lnk) na raiz do projeto.
* O próprio backend em Python detectará a ausência do build, executará o `npm install` (caso a pasta `node_modules` não exista) e o `npm run build` na pasta do dashboard de forma automática.
* Assim que a compilação finalizar, a janela do dashboard abrirá conectada diretamente ao SQLite.

---

## 🚀 Como Executar

Utilize os atalhos criados na pasta raiz:

1. [**`Visualizar_Dashboard.lnk`**](file:///D:/projects/winker/Visualizar_Dashboard.lnk): Abre a janela desktop nativa do Dashboard financeiro conectado ao banco de dados SQLite real.
2. [**`Extrair_Dados.lnk`**](file:///D:/projects/winker/Extrair_Dados.lnk): Roda a automação em Python exibindo o navegador Playwright passo a passo para extrair novos períodos de transações.
3. [**`Extrair_Dados_Headless.lnk`**](file:///D:/projects/winker/Extrair_Dados_Headless.lnk): Executa o mesmo robô de extração de dados, porém de forma invisível/silenciosa em segundo plano.

---

## 📁 Estrutura de Pastas do Projeto

O projeto está organizado da seguinte maneira:

* **[`scripts/`](file:///D:/projects/winker/scripts)**: Contém o código-fonte das automações Python.
  * `extract_winker.py`: O robô Playwright de extração.
  * `run_dashboard.py`: O backend Python exposto à interface gráfica via `pywebview`.
* **[`database/`](file:///D:/projects/winker/database)**: Contém o arquivo do banco de dados SQLite local (`winker_data.db`) utilizado pelo extrator e lido pelo dashboard.
* **[`compilados/`](file:///D:/projects/winker/compilados)**: Contém os arquivos estáticos prontos para produção do frontend gerados pelo compilador do Angular.
* **[`dashboard/`](file:///D:/projects/winker/dashboard)**: O repositório de desenvolvimento contendo o código-fonte em Angular do painel Sakai-NG.
* **[`anexos/`](file:///D:/projects/winker/anexos)**: Diretório onde o robô de extração armazena fisicamente os anexos (recibos e comprovantes em PDF/Imagens) das transações e as prestações de contas mensais de cada período.

---

## 🛠️ Arquivos Principais do Frontend (Dashboard)

Se precisar customizar a interface, a lógica ou o comportamento do painel, estes são os arquivos mais importantes localizados na pasta `dashboard/`:

1. **Estrutura Visual (HTML):**
   * [`dashboard/src/app/pages/dashboard/dashboard.html`](file:///D:/projects/winker/dashboard/src/app/pages/dashboard/dashboard.html)
     * Define o layout de página única do painel com cards de KPIs, tabelas de meses/transações, tags dinâmicas e o painel superior de filtros usando componentes do PrimeNG e Tailwind.
2. **Lógica e Integração (TypeScript):**
   * [`dashboard/src/app/pages/dashboard/dashboard.ts`](file:///D:/projects/winker/dashboard/src/app/pages/dashboard/dashboard.ts)
     * Gerencia a filtragem em tempo real, a detecção de ambiente (Modo Simulação vs. Conexão Real), formata textos do SQLite e invoca as chamadas do backend expostas pela API do `pywebview`.
3. **Roteamento da Aplicação:**
   * [`dashboard/src/app.routes.ts`](file:///D:/projects/winker/dashboard/src/app.routes.ts)
     * Define a rota raiz para carregar diretamente o componente do dashboard dentro do layout Sakai.
4. **Configurações Globais do Angular:**
   * [`dashboard/src/app.config.ts`](file:///D:/projects/winker/dashboard/src/app.config.ts)
     * Ativa o Hash Location (`withHashLocation`), eliminando erros 404 de navegação no navegador do app nativo.
   * [`dashboard/src/index.html`](file:///D:/projects/winker/dashboard/src/index.html)
     * Modifica `<base href="/">` para `./` viabilizando o carregamento relativo dos recursos locais.
   * [`dashboard/angular.json`](file:///D:/projects/winker/dashboard/angular.json)
     * Define o caminho de saída da compilação de produção (`outputPath: "../compilados"`), direcionando o build para a raiz.

