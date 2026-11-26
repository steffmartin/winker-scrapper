# Organização dos scripts

Esta pasta contém o código-fonte Python do projeto, dividido em três grupos: os entry points da aplicação, os módulos compartilhados e a suíte de testes.

## Entry points

| Arquivo | Papel |
|---|---|
| `run_dashboard.py` | Backend do dashboard, exposto à interface Angular via `pywebview`. É o processo principal da aplicação desktop. |
| `extract_winker.py` | Robô de extração (Playwright) executado de forma independente via linha de comando: `python scripts/extract_winker.py --config-file config/exemplo.config`. |

## Módulos de produção

Compartilhados entre os entry points ou carregados sob demanda pelo dashboard.

| Arquivo | Uso |
|---|---|
| `models.py` | Modelos do banco SQLite declarados com o ORM Peewee. Importado diretamente por ambos os entry points. |
| `utils.py` | Utilitários compartilhados: logger, `setup_logging` e `load_config`. Importado diretamente por ambos os entry points. |
| `setup_deps.py` | Verificação e instalação dinâmica de dependências. Importado antes das libs externas nos dois entry points. |
| `conciliacao_unificada.py` | Regras de conciliação financeira. Carregado sob demanda por `run_dashboard.py`. |
| `apresentacao_conciliacao.py` | Formatação/apresentação da conciliação unificada para o dashboard. Depende de `conciliacao_unificada.py`. |
| `relatorio_conta.py` | Relatório de extrato por conta. Carregado sob demanda por `run_dashboard.py`. |
| `relatorio_inadimplencia.py` | Relatório de inadimplência. Carregado sob demanda por `run_dashboard.py`. |
| `relatorio_recebimentos.py` | Relatório de extrato de recebimentos. Carregado sob demanda por `run_dashboard.py`. |
| `exportar_relatorio.py` | Exportação de relatórios em PDF (`salvar_pdf`). Carregado sob demanda por `run_dashboard.py`. |

> Os relatórios e a exportação de PDF usam imports tardios (dentro dos métodos da API) para reduzir o tempo de inicialização do dashboard.

## Testes

Arquivos `test_*.py` com a suíte de testes unitários. Executados de forma independente, cada um cobrindo um módulo de produção:

| Arquivo | Cobre |
|---|---|
| `test_run_dashboard.py` | API do dashboard |
| `test_revisao.py` | Fluxo de revisão de transações |
| `test_db_queries.py` | Consultas e integração com o banco |
| `test_extract_winker.py` | Extrator Winker |
| `test_fallback_condominio.py` | Fallback de identificação de condomínio no extrator |
| `test_conciliacao_unificada.py` | Regras da conciliação unificada |
| `test_extrato_recebimentos.py` | Relatório de recebimentos |
| `test_relatorio_apartamentos.py` | Relatório por apartamentos |
| `test_relatorio_conta.py` | Relatório de conta |
| `test_relatorio_inadimplencia.py` | Relatório de inadimplência |
| `test_exportar_relatorio.py` | Exportação de PDF |

## Dependências entre módulos

```
extract_winker.py ──┐
                    ├──> models.py, utils.py, setup_deps.py
run_dashboard.py ───┘         │
   │                          └──> (ORM Peewee / SQLite)
   ├──> conciliacao_unificada.py
   │        └──> apresentacao_conciliacao.py
   ├──> relatorio_conta.py ──────> models.py
   ├──> relatorio_inadimplencia.py ──> models.py
   ├──> relatorio_recebimentos.py ──> models.py
   └──> exportar_relatorio.py
```

Os entry points não se chamam entre si: o dashboard não executa o extrator e vice-versa. A integração entre os dois acontece apenas pelo banco SQLite compartilhado.
