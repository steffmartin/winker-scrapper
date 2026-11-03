# Padrões de extração e reconciliação local

Regras confirmadas em múltiplos layouts. Não são páginas, valores ou expectativas
de uma competência. Evidências mensais/decisões ficam apenas em artifacts.

## Perfis por estrutura e processamento local

Não selecionar parser pelo ano do arquivo. Há demonstrativos parciais, folhas
invertidas, tabelas sem título repetido e extratos espalhados pelo pacote. O perfil
é escolhido pelas colunas reconhecidas na imagem de cada página. Não assumir a
mesma margem, largura, ordem ou quantidade de contas/unidades entre relatórios.

- Reconhecer primeiro o cabeçalho da tabela, incluindo a coluna Unidade que
  delimita o início das datas. Um limite esquerdo de data igual a zero quando
  faltou esse cabeçalho não é evidência de uma coluna inteira: revisar localmente.
- `table_geometry.py` usa centros das palavras/datas e cabeçalhos compostos
  (Valor Pago, Valor Baixa, Conta Corrente), aceitando caixas/pontuação do OCR.
  Não usa percentuais fixos de Liquidado ou um padrão fixo de apartamento.
- A coluna de unidades tem uma leitura estreita independente, pois bordas podem
  virar números soltos no OCR de largura completa. Preservar cabeçalhos conflitantes
  como exceção; não propagar silenciosamente a unidade anterior para linhas órfãs.
- `ocr_tables.py --remove-grid` mede linhas longas e pequena inclinação local,
  conserva a variante original e registra o ângulo. Seu resultado pode ter menos
  linhas do que o original: escolher somente por menor número de erros pode omitir
  transações. Conferir a cobertura de linhas, não só a soma ou confiança OCR.
- Datas compactas/com separadores danificados só geram propostas no interior de
  colunas de data reconhecidas, com ano explícito e calendário válido. Guardar o
  token original e se houve normalização; não inferir competência dessa proposta.
- Valores sem separador decimal ficam não resolvidos. Repetir somente as células
  na fila, comparar leituras e preservar propostas sem sobrescrever as aprovadas.
- Várias contas físicas podem usar o mesmo nome no cadastro. Agrupar cadeias pelo
  cabeçalho/alias físico; se o cabeçalho falhar, separar por página e sinalizar a
  identidade pendente, em vez de concatenar contas distintas.
- Resolver alternativas bancárias somente entre triplas crédito/débito/saldo
  efetivamente lidas. Consistência numérica não autoriza criar um movimento nem
  substituir uma identidade/documento/data pelo que faria o saldo fechar.
- Mapas e ledgers já revisados são oráculos de regressão isolados. Não os alimentar
  ao parser para completar a leitura; isso daria uma falsa impressão de precisão.
  Medir recall de páginas positivas, falsos positivos e identidade de linhas como
  controles diferentes. Um teste só de páginas previamente selecionadas não mede
  precisão do classificador em todas as páginas do PDF.

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

## Variações confirmadas de título e ordem

- `DEMONSTRATIVO PARCIAL` pode trazer a mesma estrutura contábil mensal, com receitas, despesas e resumo de contas. Conferir o período e a estrutura financeira antes de reconhecer; o título isolado não basta.
- As folhas físicas de um demonstrativo podem estar invertidas. Reordenar pela paginação impressa e pelo conteúdo, preservando os números físicos como evidência.
- Carimbos próximos à paginação podem fazer PSM 3/6 retornarem texto vazio, embora a célula esteja legível. Conferir o recorte visual ou restringir a célula; não registrar ausência da página por falha do OCR.

## Colunas, controles e alternativas de OCR

- Projeção de pixels escuros pode confundir algarismos monetários alinhados com bordas. Para localizar a grade, preferir morfologia de linhas verticais longas e confirmar cabeçalhos/limites na imagem. Recalcular por página: margens e larguras mudam entre folhas do mesmo relatório.
- Comparar a posição central dos caracteres de data; caixas altas causadas pela grade criam âncoras duplicadas. Respeitar o espaçamento físico de cada tabela ao recortar uma célula, para não incluir a linha seguinte.
- Classe extraordinária ou complementar pode aparecer na segunda linha enquanto a primeira diz apenas Taxa de Condomínio. Um fechamento global correto pode esconder transferência indevida entre classes; conferir os rótulos físicos.
- Contas Recebidas pode omitir um crédito não unitário que consta no demonstrativo e no extrato. Incluir apenas após localizar valor, data, histórico e conta na fonte independente; conservar a diferença entre as fontes e sua evidência.
- Uma conta de investimento pode ter receita bruta e tarifa separadas. O aumento líquido do saldo não substitui a receita nem autoriza atribuir a despesa à corrente. Conferir os dois lados e o nome cadastrado.
- Despesas iguais do mesmo fornecedor em datas distintas podem ser duas baixas efetivas. Preservar a multiplicidade publicada e confrontar cada baixa com o banco. Liquidação zero por desconto integral não é uma despesa positiva; manter esse controle explicitamente, sem fabricar transação.
- Não substituir uma cadeia bancária já consistente só porque uma alternativa OCR coincide em parte dos campos ou no saldo. Comparar identidade, movimento e saldos anterior/seguinte; preservar a leitura original e rejeitar variantes que piorem a reconciliação.
- Um fluxo gerencial pode mostrar saldo final de conta recém-aberta sem a linha da transferência recebida. Buscar o extrato oficial daquela conta para a pergunta concreta; não criar a linha a partir da diferença de saldos.

## Identidades, referências e divergências entre fontes

- Duas linhas OCR podem apontar para o mesmo pagamento físico enquanto outro pagamento do mesmo valor foi omitido. O total continua correto: resolver as duas ocorrências na imagem e conservar o registro da correção, sem gerar ajuste financeiro.
- Um vencimento reemitido pode ocultar a referência original; confrontar histórico, demonstrativo e crédito bancário. Um mesmo dia/unidade pode ter cobrança regular e parcela de acordo com competências diferentes. Manter a identidade de cada componente antes de agregar o recebimento bancário.
- Despesas de mesmo valor/data podem se referir a NFs, tributos ou competências diferentes. Exigir classe e documento no casamento; não atribuir a referência da primeira linha compatível.
- Data da baixa analítica e data bancária podem divergir de fato. Preservar ambas na evidência e explicitar o critério de data adotado, incluindo a decisão do usuário quando houver; a conciliação não deve apagar a divergência nem trocar a competência automaticamente.
- Uma NF legível no analítico pode divergir de uma leitura OCR do demonstrativo. Conferir a imagem e registrar qual fonte sustentou o número, preservando a leitura descartada.
- Ordenação de saldos iniciais de cadastro é uma evidência local e temporal, não uma identidade permanente de investimento. Um cadastro atualizado pode inverter essa ordenação; preservar os mapeamentos confirmados pelas fontes e retirar condições antigas da configuração privada quando deixarem de se aplicar.
