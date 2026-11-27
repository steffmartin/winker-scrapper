# Winker Scraper & Dashboard Financeiro

[![Execução de Testes Unitários](https://github.com/steffmartin/winker-scrapper/actions/workflows/tests.yml/badge.svg)](https://github.com/steffmartin/winker-scrapper/actions/workflows/tests.yml)

Este projeto consiste em uma automação robusta para extração de lançamentos, transações e anexos financeiros do portal
Winker, acoplado a um Dashboard nativo para Desktop de nível premium baseado no template **Sakai PrimeNG** (Angular
v21 + PrimeNG v21 + Tailwind CSS v4).

---

## 📊 Recursos Principais do Dashboard

- **Indicadores de Gestão (KPIs):** Visualização rápida da Gestão atual, Resumo do Mês (receitas vs despesas),
  Inadimplência, Saldo de Contas e Estatísticas do Sistema.
- **Tema Dinâmico (Light/Dark Mode):** O layout é totalmente responsivo e se adapta suavemente a temas claros e escuros
  usando classes dinâmicas e gradientes do Tailwind CSS.
- **Monitoramento de Inconsistências:** O painel superior (Topbar) exibe um badge de notificação interativo sempre que
  existirem transações ou meses com divergência matemática pendentes de revisão.
- **Otimização de Performance:** Estratégias de lazy loading nativo do Angular 17+ (`@defer`) garantem que gráficos
  pesados (Chart.js), popovers e menus ocultos sejam carregados sob demanda ou em modo *idle*, mantendo o tamanho do
  pacote inicial (*initial bundle*) extremamente leve.
- **Design Premium:** Uso de Skeletons elegantes para carregamento, tipografia moderna e tolerância a dados faltantes (
  Zero-value fallbacks).

---

## 📋 Pré-requisitos

Para rodar e compilar este projeto em sua máquina local, você precisará de:

1. **Python 3.10+**: O projeto instalará outras dependências do Python, se necessário.
2. **Node.js**: Angular 21 exige Node 20.19+, 22.12+ ou 24+; necessário para instalar, testar e compilar o frontend.

---

## ⚡ Instalação e Primeira Execução

### Passo 1: Configurar Credenciais

Copie `compartilhado/config/example.config` para `compartilhado/config/meu.config` e informe suas credenciais de login no portal Winker. O arquivo `meu.config` é local e não deve ser versionado:

```json
{
  "user": "seu_usuario",
  "password": "sua_senha",
  "wl": "codigo_adm_no_winker",
  "portal_index": 1,
  "log_level": "INFO",
  "start": "2026-01",
  "end": "2026-12",
  "headless": false,
  "no_wait": true
}
```

Abaixo está o detalhamento de cada parâmetro do arquivo de configuração:

| Parâmetro      | Descrição                                                                                              | Valor Default / Padrão |
|----------------|--------------------------------------------------------------------------------------------------------|------------------------|
| `user`         | Usuário ou e-mail de login no portal Winker.                                                           | *(Obrigatório)*        |
| `password`     | Senha de login.                                                                                        | *(Obrigatório)*        |
| `wl`           | Código da administradora (`wl`) que aparece na URL de login.                                           | `""` (Vazio)           |
| `portal_index` | Posição do condomínio na lista de "Escolher Portal" caso a conta tenha acesso a múltiplos condomínios. | `1`                    |
| `log_level`    | Nível de detalhamento dos registros de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                      | `"INFO"`               |
| `start`        | Competência (Mês/Ano) inicial da extração, no formato `YYYY-MM`.                                       | Mês anterior           |
| `end`          | Competência (Mês/Ano) final da extração, no formato `YYYY-MM`.                                         | Mês atual              |
| `headless`     | Se `true`, executa o navegador oculto em segundo plano.                                                | `false`                |
| `no_wait`      | Se `true`, o terminal é encerrado imediatamente ao final, sem pedir para pressionar Enter.             | `false`                |

### Passo 2: Primeira Execução e Compilação Automática

Se você acabou de clonar este repositório do zero, a pasta de arquivos estáticos `dashboard/compilados/` não estará presente.

* Basta rodar o comando de visualização do dashboard na raiz do projeto.
* O próprio backend em Python detectará a ausência do build, executará o `npm install` (caso a pasta `node_modules` não
  exista) e o `npm run build` na pasta do dashboard de forma automática.
* Assim que a compilação finalizar, a janela do dashboard abrirá conectada diretamente ao SQLite.

---

## 🚀 Como Executar

Execute os seguintes comandos Python a partir do terminal na raiz do projeto (substitua pelo seu arquivo de
configuração):

1. **Extração de Dados**
   Roda a automação em Python para extrair novos períodos de transações.
   ```bash
   python extrator/main.py --config-file compartilhado/config/meu.config
   ```

   Se a página de informações do condomínio falhar, o extrator usa o portal ativo da sessão e o JWT obtido na página de boletos para consultar `/v1/portal`. O slug da URL é enviado a `/novo/findCondominio`; o código de segurança só é aceito quando o `id_condominio` retornado coincide com o `id_portal` da sessão. A gestão e a administradora são consultadas em `/v1/portal/{id}/about`. Se a identificação automática falhar, é solicitada a seleção manual de um condomínio cadastrado; sem seleção, a extração é interrompida e a auditoria registra a falha.
   
2. **Dashboard Financeiro**
   Abre a janela desktop nativa do Dashboard financeiro conectado ao banco de dados SQLite real.
   ```bash
   python bff/main.py
   ```


---

## 🧪 Testes Automatizados

O projeto conta com um conjunto de testes unitários automatizados para garantir o funcionamento correto de toda a lógica
pura de tratamento de dados e regras de consistência de negócios (conversão de moedas, extração de metadados das
descrições e avaliação de consistência das entidades).

Para executar os testes de backend:

```bash
python -m unittest discover -s . -p "test_*.py"
```

Para medir os gates de cobertura do Python (statements e branches):

```bash
python -m coverage run --branch --source=compartilhado,bff,extrator --omit="*/test_*.py,*/tests/*" -m unittest discover -s . -p "test_*.py"
python -m coverage json -o coverage.json --omit="*/test_*.py,*/tests/*"
```

A CI exige pelo menos 90% em statements e branches no Python e em statements, branches, functions e lines no frontend.

Para executar os testes de frontend:

```bash
cd dashboard
npm test -- --watch=false --browsers=ChromeHeadless --code-coverage
```

Os testes automatizados não acessam o portal Winker nem a base de dados real; os testes que precisam de SQLite usam bases temporárias ou em memória. O
projeto possui um pipeline de integração contínua (CI) via GitHub Actions que executa automaticamente as suítes de
testes unitários do Python e do Angular a cada push ou pull request.

## 📁 Estrutura de Pastas do Projeto

O projeto está organizado da seguinte maneira:

* **[`bff/`](bff/)**: Módulos do backend por tela e seus testes em `bff/tests/`.
* **[`extrator/`](extrator/)**: Módulos de extração e seus testes em `extrator/tests/`.
* **[`compartilhado/`](compartilhado/)**: Modelos, utilitários e dependências compartilhados; testes em `compartilhado/tests/`.
* **[`compartilhado/config/`](compartilhado/config/)**: Contém os arquivos JSON (`*.config`) de parametrização e
  credenciais para execução do scraper e inicialização do dashboard.
* **[`compartilhado/database/`](compartilhado/database/)**: Contém o arquivo do banco de dados SQLite local (
  `winker_data.db`) utilizado pelo extrator e lido pelo dashboard. Consulte o
  [`compartilhado/database/diagrama_er.md`](compartilhado/database/diagrama_er.md) para visualizar o diagrama de entidade-relacionamento completo
  das tabelas.
* **[`dashboard/compilados/`](dashboard/compilados/)**: Contém os arquivos estáticos prontos para produção do
  frontend gerados pelo compilador do Angular.
* **[`dashboard/`](dashboard)**: O repositório de desenvolvimento contendo o código-fonte em
  Angular do painel Sakai-NG.
* **[`anexos/`](anexos)**: Diretório onde o robô de extração armazena fisicamente os anexos (
  recibos e comprovantes em PDF/Imagens) das transações e as prestações de contas mensais de cada período.

---

## 🛠️ Arquivos Principais do Frontend (Dashboard)

Se precisar customizar a interface, a lógica ou o comportamento do painel, estes são os arquivos mais importantes
localizados na pasta `dashboard/`:

1. **Estrutura Visual (HTML):**
    * [
      `dashboard/src/app/pages/dashboard/dashboard.html`](dashboard/src/app/pages/dashboard/dashboard.html)
        * Define o layout principal do painel com cards de KPIs, tabelas de meses/transações, tags dinâmicas e filtros
          usando componentes do PrimeNG e Tailwind.
    * [
      `dashboard/src/app/pages/configuracoes/configuracoes.html`](dashboard/src/app/pages/configuracoes/configuracoes.html)
        * Painel visual para edição de configurações do aplicativo e preferências de tema.
    * [`dashboard/src/app/pages/notfound/notfound.ts`](dashboard/src/app/pages/notfound/notfound.ts)
        * Tela de fallback para rotas inexistentes.

2. **Lógica e Integração (TypeScript):**
    * [
      `dashboard/src/app/pages/dashboard/dashboard.ts`](dashboard/src/app/pages/dashboard/dashboard.ts)
        * Gerencia a filtragem em tempo real e consulta dados pelo BFF por meio do `pywebview`. A execução do extrator é independente.
    * [
      `dashboard/src/app/pages/configuracoes/configuracoes.ts`](dashboard/src/app/pages/configuracoes/configuracoes.ts)
        * Gerencia o estado das configurações do tema, cache e preferências do usuário.

3. **Roteamento da Aplicação:**
    * [`dashboard/src/app.routes.ts`](dashboard/src/app.routes.ts)
        * Define as rotas raiz mapeando as telas (`/`, `/configuracoes`, etc.) dentro do layout Sakai.
4. **Configurações Globais do Angular:**
    * [`dashboard/src/app.config.ts`](dashboard/src/app.config.ts)
        * Ativa o Hash Location (`withHashLocation`), eliminando erros 404 de navegação no navegador do app nativo.
    * [`dashboard/src/index.html`](dashboard/src/index.html)
        * Modifica `<base href="/">` para `./` viabilizando o carregamento relativo dos recursos locais.
    * [`dashboard/angular.json`](dashboard/angular.json)
        * Define o caminho de saída da compilação de produção (`outputPath: "compilados"`), direcionando o build para
          o diretório do frontend.

