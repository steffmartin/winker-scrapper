# Comparação preliminar da conciliação — issue 122

Consulta de 24/11/2026, com corte em 24/11/2026. O SQLite foi aberto com
`mode=ro` e `PRAGMA query_only = ON`. O resultado anterior veio diretamente
de `Api.get_inadimplencia`, com a opção desligada e sem inicializar a API
normalmente; o resultado novo veio do motor em desenvolvimento. Os valores
comparados são somas do principal por apartamento e competência, sem juros e
multa. Nenhum dado foi escrito no banco.

- Principal anterior: R$ 144.622,73.
- Principal novo: R$ 80.407,94.
- Com a toggle simulada como ativa, a tela, o relatório de inadimplência e o
  campo de saldo original do extrato retornaram R$ 80.407,94 para o mesmo
  condomínio e corte. As três chamadas usaram conexão SQLite somente leitura;
  o hash SHA-256 do arquivo permaneceu igual antes e depois das consultas.
- Grupos apartamento/competência com diferença: 254.
- A busca também permite que parte de um recebimento quite uma taxa com
  desconto e que o restante abata outra. Se a sobra permanecer sem aplicação,
  a hipótese de fracionamento é descartada para não criar desconto artificial.
- As quatro receitas negativas com apartamento e competência preenchidos
  aparecem no extrato com os valores originais negativos: R$ -1.809,72,
  R$ -992,22, R$ -30,68 e R$ -13,32. Não foram usadas para abater taxas.
- Unidade 905, competência 03/2023: anterior R$ 498,92; novo R$ 0,00. O novo
  motor identificou dois conjuntos de recebimentos de 05/04/2023 que quitam
  as três taxas com encargos; as diferenças de encargos foram R$ -0,04 e
  R$ -0,10. Outros recebimentos elegíveis da competência permanecem não
  alocados. A natureza desses valores não foi presumida.
- Unidade 504, competência 04/2023: há 34 recebimentos elegíveis. O novo
  motor encontra uma combinação antecipada para as três taxas e deixa os
  demais recebimentos como valores não alocados. Esse exemplo evidencia a
  ambiguidade que deve ser examinada na validação do critério de desempate.
- Unidade 803, competência 05/2022, corte em 12/05/2022: o cálculo anterior
  mantém a taxa 206 com principal de R$ 9,30; o novo identifica o pagamento
  20546 de R$ 9,49 e não apresenta essa taxa como inadimplente. O extrato
  preserva os dois lançamentos. Isso confirma o comportamento da convenção
  decimal implementada, sem comprovar a política efetiva do boleto.

Esta comparação é **preliminar**: o motor e os adaptadores ainda não estão
concluídos, e os casos descritos não constituem validação da origem dos
pagamentos nem da política de arredondamento do condomínio. Repetir a
comparação após as mudanças restantes e antes de considerar a issue concluída.
