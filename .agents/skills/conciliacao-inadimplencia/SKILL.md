---
name: conciliacao-inadimplencia
description: >-
  Concilia inadimplência de condomínios no winker-scrapper: usa a conciliação
  unificada do dashboard, investiga taxas, ajustes e recebimentos por unidade
  e competência, e identifica candidatos a pagamentos. Acessa o SQLite somente
  em leitura, salvo autorização explícita para alteração específica.
---

# Conciliação de inadimplência

Reproduza o resultado do dashboard com `bff/conciliacao_unificada.py` e
`bff/apresentacao_conciliacao.py`, integrados por `Api.get_inadimplencia`
em `bff/api.py`. A mesma conciliação alimenta inadimplência,
relatório e extrato. Não use a antiga toggle nem `scripts/conciliacao.py`, que
foram removidos. O antigo `inadimplencia_apartamento.py` desta pasta depende
do módulo removido e não deve ser usado como fonte de resultado.

## Segurança e acesso ao banco

O banco oficial é `compartilhado/database/winker_data.db`. Consulte em modo somente leitura,
com URI `Path(...).resolve().as_uri() + '?mode=ro'`, `uri=True` e
`PRAGMA query_only = ON`. Não leia arquivos de configuração pessoais ou
credenciais. A escrita exige autorização explícita para a alteração específica;
use transação e verifique registros antes e depois. Para testes que escrevem,
use banco temporário isolado ou em memória.

Não inicialize `Api()` normalmente sobre o banco oficial para consulta: a
inicialização pode criar tabelas ou preferências. Para usar a API, inicialize
`models.db` com a URI de leitura, aplique `query_only`, crie `Api.__new__(Api)`
e configure `init_error=None`, `condo_id` e `_tela_inadimplencia=Inadimplencia(api)`
(usando `Inadimplencia` de `bff.inadimplencia`). Evite instalação automática
ao importar: se necessário, use patch em `compartilhado.setup_deps.install_dependencies`.
Verifique o hash do banco antes e depois de consultas pela API.

## Procedimento

1. Identifique condomínio, data de corte e unidades. Consulte a API no mesmo
   corte e filtros do usuário; para a tela sem filtro, calcule o condomínio todo.
2. Examine as taxas e ajustes por apartamento e competência, e os recebimentos
   vinculados; busque também lançamentos sem unidade ou competência quando
   apropriado. Use a competência da transação, não a da prestação de contas.
3. Investigue diferenças entre principal, multa, juros, descontos e pagamentos.
   A regra informada pelo usuário é zerar encargos quando o principal zera;
   a implementação atual pode manter encargos pendentes. Confira as datas:
   descontos `D` passam a valer no seu vencimento; marcadores de renegociação
   passam a valer na data do acordo. Preserve o histórico temporal.
4. Apresente evidências e consequências de cada ajuste. Se houver autorização
   específica, efetue a mudança e recalcule o corte pelo motor atual; não
   conclua que desapareceu a inadimplência apenas porque o principal foi quitado.

O motor trabalha em centavos/Decimal, preserva vínculos e aplica arredondamento
`ROUND_HALF_DOWN`. A margem de diferença de encargos é por condomínio, convertida
para centavos e só se aplica com principal quitado; zero desativa a tolerância.
Leia o valor atual do banco, sem presumir valor fixo. A conciliação tem limites
de busca e pode sinalizar `ConciliacaoInconclusiva`; não apresente resultado
inconclusivo como completo nem suprima os limites ou validações.

Na quitação exata de um conjunto para recebimentos da mesma data, a distribuição
prioriza correspondências individuais exatas antes de fracionar outros valores.
Essa prioridade não se estende automaticamente ao caminho com ajustes históricos
ou à busca em datas distintas. Não presuma concessão de desconto à vista por
proximidade quando o pagamento é insuficiente.

No extrato, `pares` é uma apresentação das alocações calculadas, com taxas e
acréscimos à esquerda e pagamentos e descontos à direita. Movimentos da mesma
taxa, data e descrição podem ser aglutinados visualmente; confira os recebimentos
originais e seus IDs antes de inferir quantos pagamentos ocorreram. Diferença de
encargos de uma quitação conjunta não implica vínculo a uma taxa individual.

O corte do extrato completo é a data do sistema; por competência é o último dia
da competência final; por recebimento é a data final do filtro, preservando o
histórico dos grupos com movimento no intervalo. Subtotais de movimento não
são necessariamente equivalentes à inadimplência, sobretudo em cortes distintos.

## Modelo e armadilhas

- `taxas`: `C` ordinária e `E` extraordinária podem ser modelos para todas as
  unidades; `I` é individual; `P` é parcela; `D` é desconto e `R` marcador de
  renegociação. `D`/`R` vinculam-se ao item por `taxa_id`. Um `R` sobre `D`
  cancela o desconto na medida do marcador; um `R` sobre cobrança a abate.
  Vários descontos podem apontar para a mesma taxa: confira todos e seus vínculos.
- `transacoes`: receitas `tipo='R'`; `apartamento`, `competencia`, `valor`,
  `data` e `descricao` são relevantes. A competência da transação identifica a
  taxa; a competência de `meses` identifica a prestação em que foi lançada.
- Pagamentos consolidados, divididos, após o vencimento, erros de emissão e
  renegociações exigem examinar valores e datas antes de propor alterações.
  Ausência de taxa pendente isoladamente não prova pagamento.
- O motor atual pode manter encargos após quitar o principal, contrariando a
  regra informada pelo usuário. O extrato pode omitir esses encargos pendentes;
  confira a posição calculada e não trate subtotal zero como prova de quitação.
- Antes de inserir desconto confira os `D`/`R`/`P` e vínculos existentes para a
  unidade e taxa; preserve os descontos anteriores e evite duplicações. Os
  valores dos descontos são positivos e cada campo reduz o campo correspondente.
  Se houver renegociação vinculada, avalie sua interação antes de editar.

A implementação e os testes são a referência para detalhes adicionais. O
handoff `tmp/HANDOFF_ISSUE_122.md`, quando disponível, registra contexto histórico;
não pressupõe autorização para novas alterações ou reflete necessariamente o
estado atual do banco.
