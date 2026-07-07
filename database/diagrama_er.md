# Diagrama de Relacionamento do Banco de Dados

> [!NOTE]
> Banco de dados SQLite do projeto **Winker Scrapper**. O modelo relacional é gerenciado pelo ORM **Peewee** através da
> declaração de classes no arquivo `scripts/models.py`. O `ON DELETE CASCADE` garante integridade nativa nas chaves
> estrangeiras.

## Diagrama ER (Entidade-Relacionamento)

```mermaid
erDiagram
    condominio {
        TEXT id PK
        TEXT nome
        TEXT inadimplencia_data_corte
        INTEGER inadimplencia_unidades
        REAL inadimplencia_valor
        TEXT administradora
        TEXT telefone_administradora
        TEXT ultima_atualizacao
        REAL saldo_inicial
        INTEGER prazo_fechamento
    }

    meses {
        INTEGER id PK
        TEXT condominio_id FK
        TEXT exibicao
        TEXT competencia
        REAL receita_total
        REAL despesa_total
        INTEGER anexos
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    categorias {
        INTEGER id PK
        INTEGER mes_id FK
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
        TEXT extensao
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    prestacoes_contas {
        INTEGER id PK
        INTEGER mes_id FK
        TEXT caminho_local
        TEXT nome_original
        TEXT extensao
        INTEGER consistente
        TEXT motivo_inconsistencia
        INTEGER revisado_usuario
    }

    membros_gestao {
        INTEGER id PK
        TEXT condominio_id FK
        TEXT nome
        TEXT cargo
    }

    preferencias_usuario {
        INTEGER id PK
        INTEGER modo_escuro
        TEXT cor_primaria
        TEXT cor_superficie
        TEXT tema_preset
        TEXT modo_menu
        TEXT condominio_id
    }

    auditoria {
        INTEGER id PK
        TEXT condominio_id
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

    condominio ||--o{ meses: "condominio_id"
    condominio ||--o{ membros_gestao: "condominio_id"
    meses ||--o{ categorias: "mes_id"
    meses ||--o{ prestacoes_contas: "mes_id"
    categorias ||--o{ subcategorias: "categoria_id"
    subcategorias ||--o{ transacoes: "subcategoria_id"
    transacoes ||--o{ anexos: "transacao_id"
```

## Fluxo Hierárquico dos Dados

```
auditoria (Global)
preferencias_usuario (Global)
condominio  ← tabela raiz
 ├── meses
 │    ├── categorias
 │    │    └── subcategorias
 │    │         └── transacoes
 │    │              └── anexos
 │    └── prestacoes_contas
 └── membros_gestao
```

## Resumo das Tabelas

| Tabela                 | PK             | FK para            | Tipo       | Descrição                                    |
|------------------------|----------------|--------------------|------------|----------------------------------------------|
| `auditoria`            | `id` (INTEGER) | —                  | **Global** | Log de auditorias e acessos                  |
| `preferencias_usuario` | `id` (INTEGER) | —                  | **Global** | Configurações visuais do dashboard           |
| `condominio`           | `id` (TEXT)    | —                  | **Raiz**   | Dados cadastrais do condomínio               |
| `meses`                | `id` (INTEGER) | `condominio.id`    | Dependente | Período mensal com totais de receita/despesa |
| `categorias`           | `id` (INTEGER) | `meses.id`         | Dependente | Categorias financeiras por mês               |
| `subcategorias`        | `id` (INTEGER) | `categorias.id`    | Dependente | Subcategorias dentro de uma categoria        |
| `transacoes`           | `id` (INTEGER) | `subcategorias.id` | Dependente | Transações financeiras individuais           |
| `anexos`               | `id` (INTEGER) | `transacoes.id`    | Dependente | Arquivos anexados às transações              |
| `prestacoes_contas`    | `id` (INTEGER) | `meses.id`         | Dependente | Documentos de prestação de contas por mês    |
| `membros_gestao`       | `id` (INTEGER) | `condominio.id`    | Dependente | Membros da gestão condominial                |

## Observações

> [!IMPORTANT]
> - A tabela `condominio` é a **tabela raiz** do modelo de dados. Toda execução do scrapper deve preencher o
    condomínio antes de gravar dados nas tabelas dependentes.
> - `auditoria.condominio_id` é **opcional (NULL)**: o registro de auditoria é criado no início da execução, antes da
    extração do condomínio. O campo é atualizado assim que o ID é obtido.

> [!TIP]
> - Todas as tabelas possuem campos `consistente`, `motivo_inconsistencia` e `revisado_usuario`, indicando um **sistema
    de validação de dados** transversal.
> - A tabela `auditoria` é um **log de sessão** de scraping, registrando o usuário, período e dados capturados.
> - A tabela `condominio` usa `id` como TEXT (código de segurança extraído do portal Winker).
