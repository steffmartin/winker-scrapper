---
name: pdf-prestacao-contas
description: >-
  Converts condomínio Prestação de Contas PDFs into idempotent SQLite SQL scripts
  for winker-scrapper, with local page discovery, independent controls and isolated
  validation. Supports one competência or a batch/year, without production writes.
---

# PDF Prestação de Contas → SQL

Produzir SQL revisável para `meses → categorias → subcategorias → transacoes`.
Nunca executar no banco oficial sem instrução explícita. Usar conexão SQLite
`mode=ro` para consultar cadastro, esquema, motivos e criar cópia em memória.

## Organização e privacidade

- `SKILL.md`, `PATTERNS.md`, `scripts/`, `tests/` e `requirements.txt`: somente
  instruções, ferramentas reutilizáveis e testes sintéticos, versionáveis.
- `artifacts/`: tudo específico do usuário/processamento, ignorado pelo Git.
  Guardar `sources/YYYY-MM/`, `sql_scripts/`, `reports/`, `tools/YYYY/`, `tmp/`,
  `scratch_pages/`, caches, OCR, imagens, controles, ledgers, logs e entregas ali.
- Não usar `scripts/`, `sources/`, `tmp/` ou `scratch_pages/` da raiz do projeto
  para artefatos da skill. Não inserir PDFs, extratos ou dados financeiros em
  testes/documentação versionável. O histórico privado fica em
  `artifacts/reports/month-log.md`; sua ausência não impede um novo processamento.
- Retroalimentar esta skill com padrões confirmados e limitações gerais; valores,
  páginas e decisões de competências específicas pertencem apenas a artifacts.
  Não promover validação técnica a aprovação do usuário.
- Antes de processar, ler `artifacts/local-config.json`, se existir: identificação
  do condomínio, contas/mapeamentos confirmados, caminhos e instalação de OCR desta
  máquina ficam somente ali. Consultar também `artifacts/reports/month-log.md`
  quando necessário. Não copiar esses dados para arquivos versionáveis.
- Os scripts carregam essa configuração por padrão. `--config` seleciona outro
  JSON; `--condominio-id` sobrescreve o ID no gerador/validador. Sem ID explícito ou
  configurado, geração/validação falham, sem escolher um condomínio arbitrário.

## 1. Descobrir localmente antes de extrair em volume

Ler [PATTERNS.md](PATTERNS.md). Para um lote, fazer primeiro a descoberta de todos
os PDFs e dos controles brutos. Se o usuário pedir ajuda prévia para páginas
faltantes, investigar localmente e apresentar as lacunas antes do lote completo.
Não solicitar páginas/totais que já possam ser obtidos da fonte.

Da raiz do projeto:

```powershell
python .agents/skills/pdf-prestacao-contas/scripts/extract_local.py "report.pdf" --output ".agents/skills/pdf-prestacao-contas/artifacts/sources/YYYY-MM/auto" --discover-only
```

O helper não acessa banco/rede. Faz triagem textual, OCR de cabeçalhos, agrupamento
de seções e, sem `--discover-only`, OCR das tabelas selecionadas. Manifestos,
controles e candidatos ficam em disco. `RECONCILIATION_REQUIRED` é intencional:
candidatos não são lançamentos aprovados. Cache usa SHA-256 do PDF e versões do
extrator. A versão atual inventaria os cabeçalhos até o fim do documento, pois
extratos de outras contas podem aparecer depois dos comprovantes. `--scan-all`
permanece aceito por compatibilidade. Inventário de cabeçalhos não é OCR integral
de comprovantes; preservar o cache e não repetir a triagem sem mudança de fonte.

Exigir demonstrativo, recebimentos principais, sintético, analítico e extratos,
ou documentar substituto expressamente autorizado pelo usuário. Não parar no
primeiro extrato: ele pode ser de investimento e preceder o analítico. Conferir
folhas de continuação/encerramento mesmo sem título ou novas transações. Distinguir
paginação global do documento de paginação própria de cada relatório.

## 2. Extrair, normalizar e reconciliar

### Ferramentas locais reutilizáveis

Escolher o formato pela assinatura da tabela e posição dos cabeçalhos, nunca pelo
ano nem por coordenadas fixas. Além do candidato textual de `extract_local.py`,
preferir o caminho espacial em tabelas antigas ou quando houver qualquer diferença:

```powershell
python .agents/skills/pdf-prestacao-contas/scripts/ocr_tables.py --manifest "artifacts-path/auto/manifest.json" --output "artifacts-path/analysis/spatial" --pages 7 --psm 6 --dpi 300
```

Substituir os caminhos pelos artefatos privados do mês. A página é obtida do
manifesto local, não solicitada ao usuário. Para reparo de grade/inclinação, usar
`--remove-grid`; comparar com a variante original, que continua preservada. Essa
opção exige OpenCV/numpy opcionais. `--psm 6 4 3` guarda alternativas distintas;
não executar todas em todas as páginas se só uma célula estiver ruim.

`table_geometry.py` identifica colunas pelos cabeçalhos, inclusive quando mudam
de posição, ancora linhas no centro das datas e conserva valores/campos ilegíveis
como não resolvidos. Não assume lista ou regex fixa de apartamentos, ano de data
nem fórmula de condomínio. Receitas extras, indenizações, reembolsos, capital,
encargos e classes complementares não podem ser descartados por nome inesperado.
Rótulos e campos quebrados seguem para revisão local, sem herdar categoria pela
semelhança com um mês anterior.

O resultado de cada variante inclui palavras/boxes, colunas, linhas, confiança e
`repair_queue`. O cache de palavras caras é separado do reprocessamento geométrico.
Para reler apenas as células disputadas, com orçamento e retomada por cache:

```powershell
python .agents/skills/pdf-prestacao-contas/scripts/repair_cells.py --manifest "artifacts-path/auto/manifest.json" --variant "artifacts-path/analysis/spatial/VARIANT.json" --output "artifacts-path/analysis/cells" --limit 30
```

Consenso entre PSMs gera proposta, não aprovação: confrontar com os componentes da
linha, controles independentes e identidade bancária. Nunca completar centavos
ausentes a partir de saldo ou escolher a leitura apenas para fechar o total.

`reconcile_local.py --statements INPUT.json --output OUTPUT.json` verifica cadeias
por alias físico e encontra caminhos numéricos apenas entre alternativas OCR já
observadas. Dois caminhos possíveis permanecem ambíguos; nenhuma quantia é criada.
Mesmo um caminho único precisa de conferência de identidade/documento/data.
`--candidates INPUT.json --reference REVIEWED.json` compara multiplicidade e
identidades completas; referência revisada é oráculo de regressão, nunca entrada
para extrair/corrigir um mês novo. Campos ausentes não são preenchidos pela referência.

Regressão leve sem OCR/banco: `benchmark_local.py --sources ARTIFACT_SOURCES
--output AUDIT.json` compara a classificação de textos em cache com mapas de
páginas revisados. `reconcile_local.py --corpus ARTIFACT_SOURCES --output AUDIT.json`
mede as diferenças dos estágios históricos contra os ledgers finais. Usar os
resultados para escolher exceções/reparos locais; não sobrescrever fontes aprovadas.

- Preferir processamento local e devolver ao agente apenas manifestos compactos,
  diferenças e recortes disputados. Texto existente pode ser OCR antigo/ilegível.
  Rotacionar a imagem para a orientação visual correta antes do OCR.
- Começar pelas páginas principais; consultar acordos, inadimplência, extratos
  oficiais e comprovantes apenas para uma pergunta concreta. Antes de conversor
  MCP de PDF inteiro, criar PDF local só das páginas selecionadas.
- Para falha, reler somente a página/célula afetada em 300 DPI, PSM 3/4/6 ou PSM 7
  para célula; usar TSV/boxes. Grade e carimbo podem ocultar algarismos. Limiar e
  remoção de linhas são alternativas locais, não substituição automática da fonte.
  Guardar a leitura inicial e a corrigida com evidência.
- Valores vêm das colunas `Liquidado`, `Valor Pago` e `Valor Baixa`. Não usar
  último número arbitrário, valor original, saldo final ou fórmula de taxa.
  Não alterar número para forçar soma. Separar datas de vencimento/pagamento e
  referências do histórico; uma descrição pode conter uma terceira data.
- Preservar unidade entre páginas, mas confirmar cada cabeçalho por posição.
  Usar a posição da data da linha, não o mínimo de todos os boxes (bordas podem
  ter boxes altos). OCR que omite unidade pode manter o total certo e atribuí-lo
  ao apartamento anterior. Conferir por unidade, data, classe e liquidação.
- Montar controles independentes tipo → grupo → classe → centavos → página/texto,
  a partir do demonstrativo, sintético e rodapés publicados. Não fabricar controles
  somando o ledger. Conferir também os totais brutos e todos os saldos de conta
  do cadastro do condomínio; não assumir uma quantidade fixa.
- Reconciliar cada movimento/saldo intermediário do extrato corrente, recebimentos
  por unidade/data e multiplicidade de despesas por fornecedor/documento/data/valor.
  Conferir os demais investimentos, capital e saldos consolidados/entre meses.
  Validar separadamente cada conta física, mesmo quando aliases compartilham
  o nome cadastrado. O validador aceita `statement_reviewed.json` com
  `statements: [{alias, account, opening, closing, rows}]` ou a cadeia única legada;
  cada linha traz `credit`, `debit` e `balance` inteiros em centavos.
  Receitas de aplicação podem não constar no extrato corrente.

## 3. Movimentos internos e competências

- Transferências entre contas, resgates e aportes de capital não são receitas ou
  despesas econômicas. Podem constar também dos próprios relatórios de R/D.
  Confirmar origem, destino, data e valor; excluir ambos os lados, preservando a
  ponte bruto → econômico nos controles, SQL e relatório. Não classificar pelo
  nome isolado: crédito de rateio/lucros na conta capital pode ser receita real.
- Preservar a hierarquia impressa e os valores efetivamente liquidados. Não criar
  uma categoria por classe. Impostos retidos permanecem na classe do serviço.
- Não assumir que todas as unidades pagaram, nem repetir pagamento já incluído
  em Contas Recebidas por aparecer no detalhamento de acordo.
- A competência do acordo prevalece sobre dívidas originais quando o acordo está
  identificado. Vencimento reemitido comum, sozinho, não comprova acordo. Se o
  usuário autorizar repartir pelas competências originais, exigir que os créditos
  individuais somem exatamente o recebimento e conferir cada subtotal em centavos.
- Preservar adiantamentos identificados. Para conflito real entre fontes sem
  solução/instrução específica, usar `competencia = NULL` e motivo oficial
  `Competência não identificada`. A descrição não deve afirmar competência incerta.
  Não inferir competência de despesa ou receita pelo mês do pagamento. Confrontar
  referências por classe e competência com o demonstrativo; para despesas iguais,
  usar também NF/documento e tributo, evitando casamento apenas por data/valor.

## 4. Cadastro, histórico e flags

Consultar nomes e valores iniciais de `contas` com conexão read-only, no mesmo
`condominio_id` dos lançamentos. Identificar contas por evidência e pelos
mapeamentos previamente confirmados na configuração privada. Não deduzir a
função de um investimento pelo nome, saldo atual ou rendimento mensal. Uma regra
local baseada em saldos iniciais só se aplica ao cadastro em que foi confirmada;
se contas extras, saldos iguais ou falta de correspondência impedirem identificação
única, resolver sem adivinhar.
Usar o nome EXATO cadastrado; aliases do relatório não criam contas novas.
Toda transação R/D deve ter conta cadastrada, não nula nem vazia.

Conferir o condomínio configurado no banco antes de gerar. Não transportar IDs,
nomes, números de conta, saldos ou mapeamentos de outro cadastro.

Preservar em `descricao` fornecedor/beneficiário, NF/documento e histórico original
(parcela, imposto retido, identificador de serviço, produto etc.). Reunir linhas
quebradas, remover apenas ruído confirmado e conferir números de documento nas
fontes independentes. `fornecedor` separado não substitui o histórico. Não trocar
histórico por classe/categoria nem acrescentar essa classificação como boilerplate.

Ler os motivos individuais dos arrays JSON existentes no banco oficial, por tabela,
e rejeitar motivo inventado. Fonte/correção e explicação ficam em comentários e
relatório, não dentro de uma nova string de motivo.

| Situação | Valores obrigatórios |
|---|---|
| Mês sem PDF efetivamente importado | `anexos=0`, `consistente=0`, motivo `["Mês sem prestação de contas"]`, `revisado_usuario=0` |
| Despesa sem comprovante efetivamente importado | `anexos=0`, `consistente=0`, motivo inclui `Despesa sem comprovantes`, `revisado_usuario=0` |
| Campo obrigatório não identificado/conflitante | NULL quando apropriado, motivo oficial exato, flags 0 |
| Categoria/subcategoria conciliada sem discrepância própria | `consistente=1`, motivo NULL, `revisado_usuario=1` |
| Qualquer linha consistente | `revisado_usuario=1`, sem motivos |
| Qualquer linha inconsistente | `revisado_usuario=0`, motivo oficial aplicável |

Não propagar ausência de PDF/comprovantes aos agregados conciliados. Validar
`revisado_usuario = consistente` em TODAS as tabelas geradas. Não criar anexos,
caminhos ou INSERT em `prestacoes_contas` sem arquivo realmente importado e
verificado no local final, ainda que o comprovante esteja dentro do PDF fonte.

## 5. Gerar e validar isoladamente

Preparar em `artifacts/sources/YYYY-MM/`:

- `ledger.json`: lançamentos revisados com tipo, categoria, classe, data, descrição,
  `valor_centavos`, apartamento, competência, fornecedor, conta, página, evidência
  e indicação `excluded` para movimentos internos.
- `controls.json`: controles independentes revisados, mesma hierarquia, em centavos.
- `review.json`: competência, ponte bruta/econômica, decisões e notas. Só definir
  `approved_for_generation=true` depois da revisão técnica das fontes.
- Evidência de reconciliação de extratos e contas usada pelo validador.

```powershell
python .agents/skills/pdf-prestacao-contas/scripts/generate_sql.py --source ".agents/skills/pdf-prestacao-contas/artifacts/sources/YYYY-MM" --output ".agents/skills/pdf-prestacao-contas/artifacts/sql_scripts/YYYY-MM.sql"
python .agents/skills/pdf-prestacao-contas/scripts/validate_sql.py --database "database/winker_data.db" --source ".agents/skills/pdf-prestacao-contas/artifacts/sources/YYYY-MM" --sql ".agents/skills/pdf-prestacao-contas/artifacts/sql_scripts/YYYY-MM.sql" --output ".agents/skills/pdf-prestacao-contas/artifacts/sources/YYYY-MM/validation.json"
```

O gerador não executa SQL. O validador abre produção `mode=ro`, faz backup para
`:memory:`, fecha a conexão oficial e executa o SQL DUAS vezes só em memória.
Exigir FK sem erros, conteúdos/contagens lógicos idênticos, dados de outras
competências/tabelas intactos, hash do arquivo oficial inalterado, nomes de contas
exatos, motivos/JSON/flags corretos e todos os campos iguais ao ledger revisado.
Conferir transações → classes → grupos → mês e controles independentes em centavos.
Para lote anual, verificar também execução conjunta de todos os scripts solicitados e continuidade
dos saldos entre meses. Reportar explicitamente discrepâncias remanescentes.

SQL revisável: seções numeradas, palavras-chave maiúsculas, 4 espaços, valores com
duas casas, uma tupla completa por linha, INSERTs em lotes, SELECTs inline e
comentários concisos de fonte/nome/data/valor. Cleanup e lookups usam exatamente o
mês alvo. Inserir totais finais diretamente, sem incrementos provisórios. Depois
de mudar formatação/caminhos, repetir a validação isolada.

## Ambiente local e manutenção

Dependências de OCR em `requirements.txt`. Instalações e caminhos conhecidos desta
máquina ficam nas chaves `ocr.tesseract` e `ocr.tessdata` do JSON privado. Conferir
existência local; o helper aceita `--tesseract` e `--tessdata` como sobrescritas.
Sem configuração local, respeita o executável disponível no PATH e o ambiente.
Em pytesseract direto, configurar `TESSDATA_PREFIX` quando necessário. MCP OCR de
imagem aceita `image_path`/`language`; não passar PSM não suportado. PSM fica no
pytesseract local.

Testes sintéticos: `python -m unittest discover -s .agents/skills/pdf-prestacao-contas/tests -v`.
Manter gerador, validador, controles e evidência reprodutíveis. Remover apenas
scratch já revisado após verificar o caminho resolvido dentro de artifacts;
nunca apagar evidência de reconciliação nem alterar o banco oficial na limpeza.

## Checkpoint e retomada de lotes

Quando solicitado pelo usuário ou necessário para preservar uma sessão longa,
grave em `artifacts/reports/` um checkpoint com status real, arquivos canônicos e
candidatos, comandos leves de retomada, controles já conferidos, pendências,
correções com evidência e experimentos que não devem ser usados como resultado.
Indique explicitamente se SQLs ainda não foram gerados ou validados. Preserve
caches e não repita OCR integral na retomada sem uma lacuna que o justifique.
Incluir o último comando, processos ativos, resultados já concluídos e próxima
pendência concreta. Se houver adendos periódicos, atualizar o estado vivo e encerrar
o gravador ao concluir; ao retomar, não reproduzir todos os intervalos vencidos.
Checkpoint não constitui aprovação técnica nem dispensa reconciliação.
