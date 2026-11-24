---
name: conciliacao-inadimplencia
description: >-
  Concilia inadimplência de condomínios winker-scrapper: reproduz a regra do app
  (Api.get_inadimplencia), lista taxas pendentes por apartamento, encontra
  lançamentos soltos/não relacionados e inferre pagamentos candidatos.
  Acesso ao SQLite sempre em modo somente leitura, a menos que o usuário
  autorize explicitamente uma escrita.
---

# Conciliação de Inadimplência

Analisar pendências de taxa por apartamento usando **exatamente a mesma regra
do dashboard** (`Api.get_inadimplencia` em `scripts/run_dashboard.py` +
`scripts/conciliacao.py`), e apontar evidências para correção manual.

## Acesso ao banco

- Arquivo: `database/winker_data.db` na raiz do repositório. É SQLite local —
  **não há senha**; o acesso é pelo filesystem.
- Sempre abrir em leitura:

```python
import sqlite3
from pathlib import Path
p = Path(r'D:\Projects\winker-scrapper\database\winker_data.db')
con = sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True)
con.execute('PRAGMA query_only = ON')
```

- Escrita **somente com autorização explícita do usuário** para aquela ação.
  Em escrita, abrir conexão normal (`sqlite3.connect(str(p))`) e usar
  `with con:` para transação.

## Modelo de dados relevante

- `condominio`: 1 linha por condomínio. Campos úteis: `apartamentos` (JSON com
  a lista de unidades), `inadimplencia_data_corte`, `inadimplencia_unidades`,
  `inadimplencia_valor`, `tipo_juros_multa` (`M`/`J`/`N`), `taxa_renegociacao`.
- `taxas`: cobranças e ajustes. Tipos:
  - `C` taxa comum (ordinária), `E` extraordinária — templates com
    `apartamento NULL` valem para **todas** as unidades;
  - `I` individual, `P` parcela de renegociação — só do `apartamento` informado;
  - `D` desconto, `R` marcador "Renegociado:" — **nunca são cobrados**;
    seus valores são armazenados positivos. Um `R` pode apontar para uma taxa
    ou parcela, ou para um `D`. Sua ação depende do tipo do registro apontado.
  - `taxa_id` na linha `D`/`R` aponta para o `id` da cobrança descontada/
    renegociada (inclui `P` — desconto pode incidir sobre parcela).
- `renegociacao`: acordo por apartamento/faixa de competências. Gera parcelas
  `P` e marcadores `R` apontando para os itens selecionados. Um acordo novo
  pode selecionar parcelas `P` de acordos anteriores, além de taxas normais.
  Um desconto `D` só pode ser selecionado junto com sua taxa vinculada.
  Registros `P`/`R` só valem se `data_renegociacao <= data_corte`. O vencimento
  do `R` é o do item original, não a data de início do efeito do acordo.
- `meses → categorias → subcategorias → transacoes`: extrato de receitas.
  Recebimentos são `transacoes.tipo='R'`. Campos-chave da transação:
  `apartamento`, `competencia`, `valor`, `data` (`DD/MM/YYYY`), `descricao`.

### Duas "competências" diferentes (fonte clássica de confusão)

- `meses.exibicao` / `meses.competencia`: a **prestação de contas** onde o
  lançamento foi contabilizado (ex.: pagamento de competência jun/2022 pode
  entrar na prestação SET/2022).
- `transacoes.competencia`: a **competência da taxa** que o pagamento quita.
  A conciliação usa esta última.

### Regra de matching (resumo de `get_inadimplencia`)

1. Considera os `R` vigentes que apontam para um `D` e deduz seus valores do
   desconto correspondente, por apartamento e campo, com piso zero. Agrega o
   `D` remanescente e os `R` que apontam para cobranças `C`/`E`/`I`/`P`, por
   `(apartamento, taxa_id)`. Aplica essa soma às taxas em memória, com piso zero
   em `valor_original`, `desconto_vista`, `multa_percentual` e
   `juros_mes_percentual`. Isso evita aplicar novamente um desconto incluído
   no novo acordo. Antes da data do acordo, o `D` continua ativo.
2. `valor_original == 0` após abatimentos → não entra como pendente; isso não
   comprova pagamento, pois pode resultar de desconto ou renegociação.
3. Pagamentos: `transacoes` tipo `R`, `apartamento` e `competencia` não nulos,
   `data <= corte`. Agrupados por `(apartamento, competencia)`; cada pagamento
   consumido serve para uma única taxa.
4. Match unitário: valor igual a `valor_original - desconto_vista` quando
   `data_pagamento <= vencimento`, senão `valor_original` (tolerância R$0,01).
5. Sem unitário: `encontrar_combinacao` (`scripts/conciliacao.py`) procura
   subconjuntos de **≥2** lançamentos cuja soma bata no valor integral, ou no
   valor com desconto **somente se todos** os pagamentos forem até o
   vencimento. Se ocorrer `LimiteConciliacao`, a API retorna erro para a
   consulta inteira; não apresente uma lista parcial como resultado do app.
6. Pendente → calcula multa/juros: `tipo_juros_multa='M'` juros diário sobre o
   principal e multa sobre principal+juros; `'J'` multa primeiro e juros sobre
   principal+multa; `'N'` juros diário e multa sobre principal.

## Script pronto

`inadimplencia_apartamento.py` nesta pasta replica os passos 1–6 para um ou
mais apartamentos, somente leitura, e mostra os lançamentos restantes de cada
competência pendente (evidência para inferir o pagamento correto). Preserve a
ordem de processamento das taxas do app: um pagamento não pode ser consumido
duas vezes e ordenar antes da conciliação pode mudar qual taxa é considerada paga.

```bash
# um apartamento
python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --apto 204

# todos, numa data de corte específica
python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --todos --corte 2024-12-31

# com todos os recebimentos do apto agrupados por competência
python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --apto 204 --transacoes

# JSON para processamento
python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --apto 204 --json
```

Opções: `--db` (padrão `database/winker_data.db`), `--condominio` (padrão: único
cadastrado), `--apto` repetível, `--corte AAAA-MM-DD` (padrão: hoje).

## Armadilhas já observadas neste condomínio

- **Pagamento consolidado**: um único lançamento que cobre duas taxas
  (ex.: ordinária + fundo de reserva = 356,62) nunca casa — o app não divide
  valores. Solução manual: desmembrar o lançamento ou criar desconto `D`.
- **À vista pago após o vencimento**: o desconto só vale se o pagamento for até
  `vencimento` da taxa; pagar 1–2 dias depois exige o valor integral. Conferir
  se o `vencimento` da taxa bate com o do boleto (a descrição do lançamento
  costuma trazer o vencimento real).
- **Split com perna tardia**: rateio em 2+ lançamentos onde um é posterior ao
  vencimento não forma combinação com desconto.
- **Renegociação**: siga `R.taxa_id` por cada acordo e valide os itens
  selecionados individualmente, comparando cortes antes e após o acordo.
  Um `R` sobre uma parcela `P` abate essa parcela, sem apagar o histórico da
  renegociação anterior. Um `R` sobre `D` anula o desconto no cálculo a
  partir da data do novo acordo. Outras taxas podem não aparecer por pagamentos
  ou descontos: ausência na lista, isoladamente, não prova renegociação.
  A parcela `P` pode ter `D` próprio; o pagamento pode vir desmembrado.
- **`desconto_vista`/`valor_original` anômalos**: digitação errada na carga
  quebra o match mesmo com pagamento correto (ex.: 3,19/4,02 no fundo de
  reserva jan–fev/2024).
- **Pagamentos "soltos"**: buscar também `apartamento`/`competencia` nulos e
  descrições com "Unidade NNN", nome da taxa ou valores parecidos; receitas
  genéricas ("Outras Receitas", "Reembolso") geralmente não são da unidade.
- **Grupo com desconto/campanha**: valores recorrentes menores que o padrão em
  várias unidades (ex.: 67,50/75,00 em 2022) indicam desconto coletivo —
  procurar taxa `D` correspondente antes de tratar como inadimplência.

## Escrita (somente com autorização explícita)

Padrão usado para cadastrar desconto replicando campos da linha original:

```python
con = sqlite3.connect(str(DB_PATH))  # SEM mode=ro
with con:
    con.executemany('''INSERT INTO taxas
        (condominio_id, taxa_id, renegociacao_id, competencia, exibicao,
         vencimento, descricao, valor_original, desconto_vista,
         multa_percentual, juros_mes_percentual, apartamento, tipo)
        VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?)''', linhas)
```

Sempre verificar antes: ausência de `D`/`R`/`P` já existente para a mesma
`(apartamento, competencia, taxa_id)` e listar as linhas inseridas depois.
