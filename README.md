# Winker Scraper & Dashboard Financeiro

[![Execução de Testes Unitários](https://github.com/steffmartin/winker-scrapper/actions/workflows/tests.yml/badge.svg)](https://github.com/steffmartin/winker-scrapper/actions/workflows/tests.yml)

Este projeto consiste em uma automação robusta para extração de lançamentos, transações e anexos financeiros do portal
Winker, acoplado a um Dashboard nativo para Desktop de nível premium baseado no template **Sakai PrimeNG** (Angular
v21 + PrimeNG v21 + Tailwind CSS v4).

---

## 📊 Recursos Principais do Dashboard

- **Indicadores de Gestão (KPIs):** Visualização rápida da Gestão atual, Resumo do Mês (receitas vs despesas), Inadimplência, Saldo de Contas e Estatísticas do Sistema.
- **Tema Dinâmico (Light/Dark Mode):** O layout é totalmente responsivo e se adapta suavemente a temas claros e escuros usando classes dinâmicas e gradientes do Tailwind CSS.
- **Monitoramento de Inconsistências:** O painel superior (Topbar) exibe um badge de notificação interativo sempre que existirem transações ou meses com divergência matemática pendentes de revisão.
- **Otimização de Performance:** Estratégias de lazy loading nativo do Angular 17+ (`@defer`) garantem que gráficos pesados (Chart.js), popovers e menus ocultos sejam carregados sob demanda ou em modo *idle*, mantendo o tamanho do pacote inicial (*initial bundle*) extremamente leve.
- **Design Premium:** Uso de Skeletons elegantes para carregamento, tipografia moderna e tolerância a dados faltantes (Zero-value fallbacks).

---

## 📋 Pré-requisitos

Para rodar e compilar este projeto em sua máquina local, você precisará de:

1. **Python 3.10+**: O projeto instalará outras dependências do Python, se necessário.
2. **Node.js (v18+)**: Necessário apenas para realizar a compilação inicial de produção do frontend em Angular.

---

## ⚡ Instalação e Primeira Execução

### Passo 1: Configurar Credenciais

Crie o arquivo de configuração de produção ou edite o arquivo padrão de desenvolvimento localizado em `config/dev.config` na raiz do projeto, contendo suas credenciais de login no portal Winker:

```json
{
    "user": "seu_usuario",
    "password": "sua_senha",
    "wl": "codigo_adm_no_winker",
    "condo_id": "codigo_do_condominio",
    "log_level": "INFO",
    "start": "2026-01",
    "end": "2026-12",
    "headless": false,
    "no_wait": true,
    "dev": true
}
```

> O **Código do Condomínio** (`condo_id`) pode ser obtido em `https://app.winker.com.br/intra/condominio/sobre/index`.

### Passo 2: Primeira Execução e Compilação Automática

Se você acabou de clonar este repositório do zero, a pasta de arquivos estáticos `compilados/` não estará presente.

* Basta rodar o comando de visualização do dashboard na raiz do projeto.
* O próprio backend em Python detectará a ausência do build, executará o `npm install` (caso a pasta `node_modules` não
  exista) e o `npm run build` na pasta do dashboard de forma automática.
* Assim que a compilação finalizar, a janela do dashboard abrirá conectada diretamente ao SQLite.

---

## 🚀 Como Executar

Execute os seguintes comandos Python a partir do terminal na raiz do projeto (substitua pelo seu arquivo de configuração):

1. **Dashboard Financeiro**
   Abre a janela desktop nativa do Dashboard financeiro conectado ao banco de dados SQLite real.
   ```bash
   python scripts/run_dashboard.py --config-file config/dev.config
   ```

2. **Extração de Dados**
   Roda a automação em Python para extrair novos períodos de transações.
   ```bash
   python scripts/extract_winker.py --config-file config/dev.config
   ```

---

## 🧪 Testes Automatizados

O projeto conta com um conjunto de testes unitários automatizados para garantir o funcionamento correto de toda a lógica
pura de tratamento de dados e regras de consistência de negócios (conversão de moedas, extração de metadados das
descrições e avaliação de consistência das entidades).

Para executar os testes de backend:

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

Para executar os testes de frontend:

```bash
cd dashboard
npm test -- --watch=false --browsers=ChromeHeadless
```

Os testes rodam de forma 100% isolada e rápida, sem precisar interagir com a interface web ou com o banco de dados. O
projeto possui um pipeline de integração contínua (CI) via GitHub Actions que executa automaticamente as suítes de
testes unitários do Python e do Angular a cada push ou pull request.

---

## 📁 Estrutura de Pastas do Projeto

O projeto está organizado da seguinte maneira:

* **[`scripts/`](file:///D:/projects/winker/scripts)**: Contém o código-fonte das automações Python.
    * `extract_winker.py`: O robô Playwright de extração.
    * `run_dashboard.py`: O backend Python exposto à interface gráfica via `pywebview`.
    * `models.py`: Declaração do modelo do banco de dados (Tabelas) mapeadas através do ORM Peewee.
    * `setup_deps.py`: Utilitário central de verificação e instalação dinâmica de dependências.
    * `utils.py`: Funções utilitárias compartilhadas, como a configuração e centralização de logs do sistema.
    * `test_*.py`: Suíte de testes unitários de cada arquivo Python.
* **[`config/`](file:///D:/projects/winker/config)**: Contém os arquivos JSON (`*.config`) de parametrização e credenciais para execução do scraper e inicialização do dashboard.
* **[`database/`](file:///D:/projects/winker/database)**: Contém o arquivo do banco de dados SQLite local (
  `winker_data.db`) utilizado pelo extrator e lido pelo dashboard. Consulte o
  [`database/diagrama_er.md`](database/diagrama_er.md) para visualizar o diagrama de entidade-relacionamento completo
  das tabelas.
* **[`compilados/`](file:///D:/projects/winker/compilados)**: Contém os arquivos estáticos prontos para produção do
  frontend gerados pelo compilador do Angular.
* **[`dashboard/`](file:///D:/projects/winker/dashboard)**: O repositório de desenvolvimento contendo o código-fonte em
  Angular do painel Sakai-NG.
* **[`anexos/`](file:///D:/projects/winker/anexos)**: Diretório onde o robô de extração armazena fisicamente os anexos (
  recibos e comprovantes em PDF/Imagens) das transações e as prestações de contas mensais de cada período.

---

## 🛠️ Arquivos Principais do Frontend (Dashboard)

Se precisar customizar a interface, a lógica ou o comportamento do painel, estes são os arquivos mais importantes
localizados na pasta `dashboard/`:

1. **Estrutura Visual (HTML):**
    * [`dashboard/src/app/pages/dashboard/dashboard.html`](file:///D:/projects/winker/dashboard/src/app/pages/dashboard/dashboard.html)
        * Define o layout principal do painel com cards de KPIs, tabelas de meses/transações, tags dinâmicas e filtros usando componentes do PrimeNG e Tailwind.
    * [`dashboard/src/app/pages/configuracoes/configuracoes.html`](file:///D:/projects/winker/dashboard/src/app/pages/configuracoes/configuracoes.html)
        * Painel visual para edição de configurações do aplicativo e preferências de tema.
    * [`dashboard/src/app/pages/notfound/notfound.html`](file:///D:/projects/winker/dashboard/src/app/pages/notfound/notfound.html)
        * Tela de fallback amigável caso uma rota inexistente seja acessada.

2. **Lógica e Integração (TypeScript):**
    * [`dashboard/src/app/pages/dashboard/dashboard.ts`](file:///D:/projects/winker/dashboard/src/app/pages/dashboard/dashboard.ts)
        * Gerencia a filtragem em tempo real e invoca as chamadas de extração de dados expostas pela API do `pywebview`.
    * [`dashboard/src/app/pages/configuracoes/configuracoes.ts`](file:///D:/projects/winker/dashboard/src/app/pages/configuracoes/configuracoes.ts)
        * Gerencia o estado das configurações do tema, cache e preferências do usuário.

3. **Roteamento da Aplicação:**
    * [`dashboard/src/app.routes.ts`](file:///D:/projects/winker/dashboard/src/app.routes.ts)
        * Define as rotas raiz mapeando as telas (`/`, `/configuracoes`, etc.) dentro do layout Sakai.
4. **Configurações Globais do Angular:**
    * [`dashboard/src/app.config.ts`](file:///D:/projects/winker/dashboard/src/app.config.ts)
        * Ativa o Hash Location (`withHashLocation`), eliminando erros 404 de navegação no navegador do app nativo.
    * [`dashboard/src/index.html`](file:///D:/projects/winker/dashboard/src/index.html)
        * Modifica `<base href="/">` para `./` viabilizando o carregamento relativo dos recursos locais.
    * [`dashboard/angular.json`](file:///D:/projects/winker/dashboard/angular.json)
        * Define o caminho de saída da compilação de produção (`outputPath: "../compilados"`), direcionando o build para
          a raiz.

