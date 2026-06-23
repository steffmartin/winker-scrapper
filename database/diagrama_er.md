# Diagrama de Relacionamento do Banco de Dados

> [!NOTE]
> Banco de dados SQLite do projeto **Winker Scrapper**. As relações foram inferidas a partir das chaves estrangeiras presentes nos campos de cada tabela.

## Diagrama ER (Entidade-Relacionamento)

```mermaid
erDiagram
    meses {
        TEXT id PK
        TEXT exibicao
        REAL receita_total
        REAL despesa_total
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    categorias {
        INTEGER id PK
        TEXT mes_id FK
        TEXT tipo
        TEXT nome
        REAL valor
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    subcategorias {
        INTEGER id PK
        INTEGER categoria_id FK
        TEXT tipo
        TEXT nome
        REAL valor
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    transacoes {
        INTEGER id PK
        INTEGER subcategoria_id FK
        TEXT tipo
        TEXT data
        TEXT descricao
        REAL valor
        TEXT apartamento
        TEXT competencia
        TEXT fornecedor
        INTEGER consistente
        INTEGER anexos
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
        TEXT conta
    }

    anexos {
        INTEGER id PK
        INTEGER transacao_id FK
        TEXT caminho_local
        TEXT nome_original
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    prestacoes_contas {
        INTEGER id PK
        TEXT mes_id FK
        TEXT caminho_local
        TEXT nome_original
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    condominio {
        TEXT id PK
        TEXT nome
        TEXT inadimplencia_data_corte
        INTEGER inadimplencia_unidades
        REAL inadimplencia_valor
        TEXT administradora
        TEXT telefone_administradora
    }

    membros_gestao {
        INTEGER id PK
        TEXT nome
        TEXT cargo
    }

    auditoria {
        INTEGER id PK
        TEXT usuario_uuid
        INTEGER usuario_id
        TEXT usuario_name
        TEXT usuario_cpf
        TEXT usuario_rg
        TEXT usuario_fone
        TEXT usuario_apto
        TEXT data_hora_captura
        TEXT ip
        TEXT mac
        TEXT periodo_inicio
        TEXT periodo_fim
        INTEGER downloads_realizados
        INTEGER transacoes_lidas
        REAL tempo_duracao
        INTEGER capturou_condominio
        INTEGER capturou_inadimplencia
        INTEGER capturou_membros
    }

    meses ||--o{ categorias : "mes_id"
    meses ||--o{ prestacoes_contas : "mes_id"
    categorias ||--o{ subcategorias : "categoria_id"
    subcategorias ||--o{ transacoes : "subcategoria_id"
    transacoes ||--o{ anexos : "transacao_id"
```

## Fluxo Hierárquico dos Dados

```
meses
 ├── categorias  (mes_id → meses.id)
 │    └── subcategorias  (categoria_id → categorias.id)
 │         └── transacoes  (subcategoria_id → subcategorias.id)
 │              └── anexos  (transacao_id → transacoes.id)
 └── prestacoes_contas  (mes_id → meses.id)

Tabelas independentes:
 ├── condominio      (dados cadastrais do condomínio)
 ├── membros_gestao  (membros da gestão do condomínio)
 └── auditoria       (log de acesso/captura dos dados)
```

## Resumo das Tabelas

| Tabela | PK | Tipo | Descrição |
|---|---|---|---|
| `meses` | `id` (TEXT) | Principal | Período mensal com totais de receita/despesa |
| `categorias` | `id` (INTEGER) | Dependente | Categorias financeiras por mês |
| `subcategorias` | `id` (INTEGER) | Dependente | Subcategorias dentro de uma categoria |
| `transacoes` | `id` (INTEGER) | Dependente | Transações financeiras individuais |
| `anexos` | `id` (INTEGER) | Dependente | Arquivos anexados às transações |
| `prestacoes_contas` | `id` (INTEGER) | Dependente | Documentos de prestação de contas por mês |
| `condominio` | `id` (TEXT) | Independente | Dados cadastrais do condomínio |
| `membros_gestao` | `id` (INTEGER) | Independente | Membros da gestão condominial |
| `auditoria` | `id` (INTEGER) | Independente | Log de auditorias e acessos |

## Observações

> [!TIP]
> - Todas as tabelas possuem campos `consistente`, `motivo_inconsistencia` e `revisado_usuario`, indicando um **sistema de validação de dados** transversal.
> - A tabela `auditoria` é um **log de sessão** de scraping, registrando o usuário, período e dados capturados.
> - A tabela `condominio` usa `id` como TEXT (possivelmente um slug ou código externo).
