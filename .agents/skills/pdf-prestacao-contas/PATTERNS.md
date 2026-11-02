# Padrões de extração e reconciliação local

Regras confirmadas em múltiplos layouts. Não são páginas, valores ou expectativas
de uma competência. Evidências mensais/decisões ficam apenas em artifacts.

## Identificar a função, não apenas o título

| Função | Assinaturas/colunas | Cuidados |
|---|---|---|
| Demonstrativo | DEMONSTRATIVO DE RECEITAS E DESPESAS, HISTÓRICO, Mês Ref., valores, RESUMO/CONTAS CORRENTES | Grupos RECEITAS/DESPESAS definem hierarquia; rótulos TOTAL DE RECEITAS/DESPESAS prevalecem sobre maior valor. SALDO A SER TRANSFERIDO não é despesa. |
| Recebimentos | CONTAS RECEBIDAS, filtro Unidade: todas, Vencimento, Pagamento, Liquidado, Conta Corrente, Descrição | Uma linha por classe liquidada. Ler não-unidades antes dos apartamentos: aplicações, cashback, depósitos, capital etc. O rodapé Classe de Conta é controle, não outro lançamento. |
| Sintético | SINTÉTICO DE DESPESAS, Grupo/Classe, Valor Lcto, Juros, Multa, Desconto, Valor Baixa | Controle independente por classe/grupo; usar Valor Baixa e os cabeçalhos renderizados para ordenar juros/multa/desconto. |
| Analítico | DESPESAS POR GRUPO E CLASSE, Fornecedor, Pagamento, Valor Lcto, Valor Pago, Descrição | Grupo/classe podem continuar sem repetir título. Fornecedor/NF e descrição podem quebrar em linhas distintas. Total Classe/Grupo/Condomínio nunca é transação. |
| Extrato gerencial | FLUXO DE CAIXA, conta/número, Data, Crédito, Débito, Saldo Inicial/Final | Exclusivamente controle independente. Pode haver vários extratos de investimento antes do analítico/corrente. Conferir todos os movimentos e saldos. |
| Acordos | Unidade, parcelas, valor acordado/liquidado, RELAÇÃO DAS CONTAS ORIGINAIS | Documento emitido ou parcela futura não prova pagamento. Pode repetir receita já na lista principal. Competência do acordo só prevalece quando há acordo identificado. |
| Recebimentos auxiliares | CONTAS RECEBIDAS com filtro de uma unidade, poucas linhas | Não unir automaticamente à lista principal. Comparar unidade/data/valor e multiplicidade. |
| Inadimplência | UNIDADES INADIMPLENTES, vencimento, cobrança | Apoio, nunca fonte de recebimento. |
| Extrato oficial/comprovante | Banco/documentos sem assinatura completa do relatório gerencial | Consultar para dúvida concreta; pode resolver erro de lançamento no próprio extrato gerencial. |

Capas e sumários repetem títulos e colunas mencionadas; exigir estrutura de tabela.
OCR pode danificar SUMÁRIO e preservar os títulos: múltiplos títulos sem datas e
sem valores não são tabela financeira. Cabeçalho de emissão pode estar no mês
seguinte; o período do relatório define a competência do pacote.

## Paginação, orientação e completude

- Conferir paginação em célula renderizada, títulos, sequência e rodapé final.
  Paginação global atravessa seções e pode ter offset em relação ao PDF físico;
  não tratá-la como denominador de cada tabela nem fabricar folhas faltantes.
- Uma última folha pode conter só notas e assinaturas. Uma continuação pode não
  repetir grupo/classe. Título não reconhecido não significa ausência da página.
- Não encerrar no primeiro saldo final se ainda faltam relatórios/contas. Se o
  sintético estiver realmente ausente, obter instrução do usuário sobre controles
  substitutos (demonstrativo + subtotais analíticos), sem fingir que foi encontrado.
- A camada textual pode conter OCR antigo, especialmente em tabelas deitadas.
  A rotação declarada não basta: conferir a orientação visual. Se nenhuma rotação
  classificar o título da continuação, guardar a melhor leitura, não a última.

## Reparar somente o necessário

Guardar texto, variantes, TSV/boxes, controles e exceções em disco. Comparar
leituras por célula/linha e controles independentes, nunca por comprimento de texto.
Limiar que ajuda um relatório pode apagar vírgulas/datas em outro. Grade e carimbo
podem deixar somente o final do valor: localizar a coluna Liquidado/Valor Pago.
Moeda tem duas casas, mas OCR sem separador precisa de conferência, não aplicação
de fórmula da taxa. Regra de juros/desconto jamais prova que uma unidade pagou.

Cabeçalho de unidade pode ser omitido ou confundido com outra unidade. Recorte
esquerdo PSM 6/11, posição da data e inspeção da imagem ajudam. Manter ordem física
e conferir quantidade de linhas de cada bloco. Não trocar identificação para
forçar extrato: conferir o cabeçalho efetivamente impresso.

Normalização de datas não pode começar dentro de outra data ou parcela. Descrição
com data adicional não muda as duas colunas vencimento/pagamento. Conservar conta,
competência, histórico e contexto através das páginas, inclusive quando uma linha
tem conta ou NF impressa acima/abaixo.

## Controles que não se substituem

1. Brutos publicados: demonstrativo, resumo e rodapés finais.
2. Hierarquia: classes e grupos independentes, separados da soma dos lançamentos.
3. Identidade: unidade/data/competência/valor e fornecedor/NF/data/valor pago.
4. Banco: cada movimento, saldo intermediário, capital e transferências.
5. Contas: saldo anterior + créditos - débitos ± transferências = saldo final;
   soma consolidada e continuidade entre competências.

Um total correto pode esconder duas atribuições erradas. Igualdade interna do SQL
ou do saldo líquido não prova completude. Conservar a ponte bruto → econômico
e erros da fonte documentados; não criar lançamento de ajuste sem autorização.

Fornecedor deve continuar na descrição, junto com documento e histórico (parcelas,
identificadores, tributos, serviço ou item). Conferir NFs entre analítico e
demonstrativo; OCR pode acrescentar algarismo ou perder a NF numa linha quebrada.
Não transportar ajustes, exclusões extraordinárias ou competências decididas por
usuário de uma competência para outra.
