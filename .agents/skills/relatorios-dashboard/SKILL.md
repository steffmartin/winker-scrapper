---
name: relatorios-dashboard
description: Criar ou manter relatórios da página Relatórios do dashboard winker-scrapper seguindo os padrões de filtros, geração, backend, totais, agrupamento, impressão e PDF.
---

# Relatórios do dashboard

Use esta skill para criar ou alterar relatórios da página **Relatórios**. Antes de alterar um relatório, leia seu componente e sua função de backend: as regras de negócio variam. Instruções mais recentes do usuário prevalecem sobre este padrão.

## Arquitetura e carregamento

- A página compartilhada fica em `dashboard/src/app/pages/relatorios/relatorios.ts` e `relatorios.html`. A rota e o menu Home apontam para ela.
- Cada relatório tem componente Angular standalone e template próprios, no diretório de relatórios. Registre-o no seletor e carregue o componente por `import()` **somente depois de selecionado**, seguindo `alterarRelatorio()`. Use `NgComponentOutlet` com `modo: 'formulario'` ou `modo: 'resultado'` e o callback `aoGerar`.
- Busque opções de filtros apenas quando o relatório que as utiliza for selecionado. Não carregue dados ou templates dos demais relatórios na inicialização. Reutilize `get_apartamentos` e `get_contas_relatorio` quando aplicável; não busque todas as configurações apenas para preencher uma lista.
- Cada relatório tem função própria exposta pela classe `Api` em `scripts/run_dashboard.py`. Ela recebe filtros, retorna `{status, data}` ou `{status, message}` e pode delegar a um módulo `scripts/relatorio_*.py`. Reutilize funções existentes sem modificá-las quando esse for o escopo: por exemplo, `get_relatorio_inadimplencia` chama `get_inadimplencia` e formata a resposta.
- O backend é responsável por validação, seleção de dados, regras de negócio, conciliação, agrupamento, ordenação e cálculos monetários, incluindo totais e subtotais. Retorne valores prontos ao frontend e isole os dados por condomínio. Use centavos/`Decimal` nas somas monetárias. Ajustes calculados apenas para um relatório não são persistidos.
- O frontend formata e apresenta a resposta; pode aplicar estilos, como tachado de renegociados. Não replique cálculos financeiros ou agrupamentos no template nem altere regras de outros fluxos apenas para atender um relatório.

## Página e filtros

- A entrada **Relatórios** fica na seção Home, abaixo de Inadimplência. O card superior tem título à esquerda e seletor no extremo direito. Sem seleção, exiba o estado vazio no padrão da página de Inadimplência.
- Ao selecionar um relatório, mostre somente seus filtros. Siga Configurações: `grid grid-cols-1 md:grid-cols-3 gap-6`, rótulos acima dos campos; um controle pode ocupar as três colunas (`md:col-span-3`). O botão **Gerar** fica em linha própria, alinhado à direita.
- Use PrimeNG e os padrões existentes de intervalo, calendário, multisseleção e português. Em filtros opcionais de múltiplas opções, nenhuma seleção significa todos, salvo regra específica. Ao limpar um `p-multiSelect`, trate `null` como lista vazia; apresente o placeholder apenas uma vez e resuma múltiplas seleções em português.
- A validação de parâmetros obrigatórios pertence ao backend; o frontend mostra o erro retornado. Trate carregamento e falhas das opções, com nova tentativa, sem representar falha como lista vazia válida.
- Ao gerar novamente, remova imediatamente o resultado anterior e exiba skeleton. Mostre erros e impeça que respostas antigas substituam a seleção ou geração mais recente. Congele uma cópia dos filtros usados: editar o formulário depois não altera os parâmetros do resultado já gerado.

## Resultado, impressão e PDF

- Exiba o resultado na mesma página, em **outro card abaixo do card Relatórios**. O título é o nome do relatório; à direita ficam as ações comuns por ícone para salvar PDF e imprimir. Preserve os controles compartilhados em `relatorios.ts`/`.html`, com toast para sucesso/erro e tratamento do cancelamento.
- Logo abaixo do título, apresente em um quadro com borda todos os parâmetros efetivamente usados, incluindo padrões e valores inferidos, sem rotulá-los como inferidos ou não selecionados. Para filtro vazio, mostre, por exemplo, “Todos”. Inclua data de corte quando aplicável.
- Depois do quadro, renderize o HTML específico. Mantenha colunas alinhadas entre grupos equivalentes, estados vazios claros e agrupamentos/ordenações fornecidos pelo backend.
- O **Total geral** fica ao final, alinhado à direita, em negrito e separado por linha superior. Mostre os subtotais definidos para cada relatório; não confunda movimento do período com saldo. No extrato de conta, o total geral soma os saldos finais das contas incluídas no relatório.
- A impressão inclui somente o card de resultado e seu título, sem filtros nem ações. O PDF usa o seletor nativo e a mesma visualização de impressão. Preserve o padrão paisagem e os estilos em `dashboard/src/assets/styles.scss` e `scripts/exportar_relatorio.py`. A janela nativa de impressão é controlada pelo sistema.

## Relatórios existentes: não generalizar suas regras

- **Extrato de recebimentos:** `scripts/relatorio_recebimentos.py` e `extrato-recebimentos.*`. Filtros: tipo Completo/Por competência/Por recebimento, período quando aplicável e apartamentos. Agrupamento: apartamento → competência, incluindo “Sem competência” quando aplicável; na competência, cobranças antes de recebimentos, data crescente e valor decrescente. A conciliação é específica deste relatório, não a geral do sistema. Descontos à vista e acréscimos são linhas apenas do relatório, datadas pelo recebimento; registros renegociados ficam tachados e não participam da conciliação nem dos subtotais. Há subtotal por competência, por apartamento e total geral.
- **Inadimplência:** `scripts/relatorio_inadimplencia.py` e `relatorio-inadimplencia.*`. Filtros: apartamentos e data de corte. A função exclusiva chama `get_inadimplencia`; mostra os valores retornados sem colunas de juros e multa, agrupados por apartamento → competência, ordenados por vencimento crescente e valor decrescente. Subtotais por competência e apartamento e total geral vêm do backend. A conciliação existente tem limitações acompanhadas na issue #95; não presuma que este relatório as corrige.
- **Extrato de conta:** `scripts/relatorio_conta.py` e `extrato-conta.*`. Filtros: intervalo diário e contas; inicialmente, primeiro dia do mês atual até hoje. Agrupamento: conta → mês; ordenação por data crescente e valor decrescente. Mostre saldo anterior e final por conta, saldo por lançamento e subtotal mensal. Destaque somente a data e o saldo do último lançamento de cada dia. O total geral soma os saldos finais das contas incluídas. Transferências ainda dependem da issue #73; não as invente nem suponha que estejam incluídas.

## Verificação

- Cubra no backend os filtros, isolamento por condomínio, ordenação, grupos vazios, limites, erros e totais próprios da mudança; no frontend, teste apresentação, geração, estados de carregamento/erro e filtros relevantes. Consulte `scripts/test_relatorio_*.py`, `scripts/test_extrato_recebimentos.py` e `dashboard/src/app/pages/relatorios/relatorios.spec.ts`.
- Execute testes pertinentes e `npm run build` em `dashboard` quando houver mudança de frontend. Confirme no build que componentes de relatório têm chunks próprios e permanecem sob demanda. Mocks não comprovam o comportamento real do diálogo nativo ou do WebView2; informe essa limitação quando relevante.
