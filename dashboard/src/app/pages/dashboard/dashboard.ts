import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, registerLocaleData } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LayoutService } from '@/app/layout/service/layout.service';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { TagModule } from 'primeng/tag';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { TooltipModule } from 'primeng/tooltip';
import { TreeTableModule } from 'primeng/treetable';
import { DatePickerModule } from 'primeng/datepicker';
import { ToolbarModule } from 'primeng/toolbar';
import localePt from '@angular/common/locales/pt';

registerLocaleData(localePt);

interface DashboardStats {
    total_receitas: number;
    total_despesas: number;
    total_meses: number;
    total_transacoes: number;
    total_inconsistencias: number;
    total_anexos: number;
    total_prestacoes: number;
}

interface Month {
    id: string;
    exibicao: string;
    receita_total: number;
    despesa_total: number;
    consistente: number;
    motivo_inconsistencia: string | null;
}

interface Transaction {
    transacao_id: number;
    tipo: string;
    data: string;
    descricao: string;
    valor: number;
    apartamento: string | null;
    competencia: string | null;
    fornecedor: string | null;
    conta?: string | null;
    qtde_anexos_original: number;
    consistente: number;
    motivo_inconsistencia: string | null;
    subcategoria_nome: string;
    categoria_nome: string;
    mes_exibicao: string;
    mes_id: string;
}

interface SelectOption {
    label: string;
    value: any;
}

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        TableModule,
        ButtonModule,
        CardModule,
        TagModule,
        InputTextModule,
        SelectModule,
        TooltipModule,
        TreeTableModule,
        DatePickerModule,
        ToolbarModule
    ],
    templateUrl: './dashboard.html',
    styles: [`
        :host ::ng-deep .p-datatable-row-expansion > td {
            padding: 0 !important;
        }
        :host ::ng-deep .nested-table-cell {
            padding: 0 !important;
        }
    `]
})
export class Dashboard implements OnInit {
    layoutService = inject(LayoutService);

    // Estado do Banco de Dados
    dbStatusText = 'Carregando...';
    dbStatusSeverity: 'success' | 'info' | 'warn' | 'danger' | 'secondary' = 'info';

    // Estatísticas (Cards)
    stats: DashboardStats = {
        total_receitas: 0,
        total_despesas: 0,
        total_meses: 0,
        total_transacoes: 0,
        total_inconsistencias: 0,
        total_anexos: 0,
        total_prestacoes: 0
    };

    // Coleções de Dados
    months: Month[] = [];
    transactions: Transaction[] = [];
    filteredTransactions: Transaction[] = [];

    // Filtros
    searchQuery = '';
    selectedMonth: string | null = null;
    selectedType: string | null = null;
    selectedConsistency: number | null = null;

    // Opções dos Dropdowns
    filterMonthOptions: SelectOption[] = [{ label: 'Todos', value: null }];
    filterTypeOptions: SelectOption[] = [
        { label: 'Todos', value: null },
        { label: 'Receita', value: 'R' },
        { label: 'Despesa', value: 'D' }
    ];
    filterConsistencyOptions: SelectOption[] = [
        { label: 'Todos', value: null },
        { label: 'Consistente', value: 1 },
        { label: 'Inconsistente', value: 0 }
    ];

    // Modo Mock ativo caso esteja fora do pywebview
    isMockMode = false;

    // Componentes para a Tabela de Detalhamento Mensal
    treeTableValue = signal<any[]>([]);
    cols = [
        { field: 'nome', header: 'Descrição / Nome' },
        { field: 'receita', header: 'Receita (R$)' },
        { field: 'despesa', header: 'Despesa (R$)' },
        { field: 'detalhe', header: 'Vínculos / Detalhes' },
        { field: 'docs', header: 'Ações / Comprovantes' }
    ];
    activeMonthId: string | null = null;
    activeMonthName = '';
    selectedDate: Date | null = null;
    viewMode: 'tree' | 'expansion' = 'tree';
    expandedMonthRows: { [key: string]: boolean } = {};
    expandedCatRows: { [key: string]: boolean } = {};

    onDateSelect(date: Date) {
        if (!date) return;
        const year = date.getFullYear();
        const monthNum = String(date.getMonth() + 1).padStart(2, '0');
        const targetId = `${year}-${monthNum}`; // O banco usa YYYY-MM
        
        // Procura se esse mês existe na nossa lista
        const found = this.months.find(m => m.id.replace('-', '').replace('_', '') === `${year}${monthNum}` || m.id === targetId || m.id === `${year}${monthNum}`);
        if (found) {
            this.selectMonthNode(found.id);
        } else {
            alert(`Nenhum dado encontrado para o período ${monthNum}/${year}.`);
        }
    }

    selectMonthNode(monthId: string) {
        this.activeMonthId = monthId;
        const m = this.months.find(x => x.id === monthId);
        this.activeMonthName = m ? m.exibicao : '';
        
        // Atualiza a data selecionada no DatePicker
        const parts = monthId.split('-');
        if (parts.length === 2) {
            this.selectedDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
        } else {
            // Caso venha YYYYMM
            const y = parseInt(monthId.substring(0, 4));
            const mo = parseInt(monthId.substring(4, 6)) - 1;
            this.selectedDate = new Date(y, mo, 1);
        }

        if (this.isMockMode) {
            const mockTree = this.getMockMonthlyTree(monthId);
            this.treeTableValue.set(mockTree);
            this.initializeExpandedRows(mockTree);
        } else {
            const api = (window as any).pywebview.api;
            api.get_monthly_tree(monthId).then((res: any) => {
                if (res.status === 'success') {
                    this.treeTableValue.set([res.data]);
                    this.initializeExpandedRows([res.data]);
                } else {
                    alert('Erro ao carregar detalhamento: ' + res.message);
                }
            });
        }
    }

    initializeExpandedRows(data: any[]) {
        const monthRows: { [key: string]: boolean } = {};
        const catRows: { [key: string]: boolean } = {};
        
        data.forEach(monthNode => {
            if (monthNode && monthNode.data && monthNode.data.id) {
                monthRows[monthNode.data.id] = true;
            }
            if (monthNode && monthNode.children) {
                monthNode.children.forEach((catNode: any) => {
                    if (catNode && catNode.data && catNode.data.id) {
                        catRows[catNode.data.id] = true;
                    }
                });
            }
        });
        
        this.expandedMonthRows = monthRows;
        this.expandedCatRows = catRows;
    }

    getMockMonthlyTree(monthId: string) {
        const m = this.months.find(x => x.id === monthId);
        const monthExibicao = m ? m.exibicao : 'Mês Simulado';
        
        const monthStats = {
            id: 'mes_' + monthId,
            nome: monthExibicao,
            receita_total: m ? m.receita_total : 0.0,
            despesa_total: m ? m.despesa_total : 0.0,
            consistente: m ? m.consistente : 1,
            motivo_inconsistencia: m ? m.motivo_inconsistencia : null,
            nivel: 1
        };

        // Filtra as transações para esse mês
        const monthTx = this.transactions.filter(t => t.mes_id === monthId);

        // Agrupamento por Categorias e Subcategorias
        const categoriesMap = new Map<string, any>();
        const seenTxKeys = new Set<string>();

        monthTx.forEach(tx => {
            // Chave composta para desduplicar transações no mock caso venham duplicadas do banco
            const txKey = `${tx.data}_${tx.descricao}_${tx.valor}_${tx.apartamento || ''}_${tx.tipo}`;
            if (seenTxKeys.has(txKey)) {
                return;
            }
            seenTxKeys.add(txKey);

            const catKey = tx.categoria_nome;
            if (!categoriesMap.has(catKey)) {
                categoriesMap.set(catKey, {
                    nome: catKey,
                    tipo: tx.tipo,
                    valor: 0.0,
                    consistente: 1,
                    motivo_inconsistencia: null,
                    subcategoriesMap: new Map<string, any>()
                });
            }
            const cat = categoriesMap.get(catKey);
            cat.valor += tx.valor;
            if (tx.consistente === 0) {
                cat.consistente = 0;
            }

            const subKey = tx.subcategoria_nome;
            if (!cat.subcategoriesMap.has(subKey)) {
                cat.subcategoriesMap.set(subKey, {
                    nome: subKey,
                    tipo: tx.tipo,
                    valor: 0.0,
                    consistente: 1,
                    motivo_inconsistencia: null,
                    transactions: []
                });
            }
            const sub = cat.subcategoriesMap.get(subKey);
            sub.valor += tx.valor;
            if (tx.consistente === 0) {
                sub.consistente = 0;
            }

            sub.transactions.push({
                data: {
                    id: 'tx_' + tx.transacao_id,
                    nome: tx.descricao,
                    valor: tx.valor,
                    tipo: tx.tipo,
                    consistente: tx.consistente,
                    motivo_inconsistencia: tx.motivo_inconsistencia,
                    detalhe: tx.apartamento ? 'Apto ' + tx.apartamento : '',
                    data: tx.data,
                    anexos: tx.qtde_anexos_original,
                    nivel: 4
                }
            });
        });

        // Monta os nós finais
        const catNodes: any[] = [];
        let catIndex = 1;

        const sortedCategories = Array.from(categoriesMap.entries()).sort((a, b) => {
            const aTipo = a[1].tipo;
            const bTipo = b[1].tipo;
            if (aTipo !== bTipo) {
                return aTipo === 'R' ? -1 : 1;
            }
            // Mesmo tipo, ordenar por valor decrescente
            return b[1].valor - a[1].valor;
        }) as [string, any][];

        sortedCategories.forEach(([catName, catVal]) => {
            const subNodes: any[] = [];
            let subIndex = 1;

            const sortedSubcategories = Array.from(catVal.subcategoriesMap.entries()).sort((a: any, b: any) => {
                // Ordenar por valor decrescente
                return b[1].valor - a[1].valor;
            }) as [string, any][];

            sortedSubcategories.forEach(([subName, subVal]) => {
                // Ordenar as transações do mock por data crescente
                subVal.transactions.sort((a: any, b: any) => {
                    const parseDate = (dStr: string) => {
                        if (!dStr) return 0;
                        const parts = dStr.split('/');
                        if (parts.length === 3) {
                            return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0])).getTime();
                        }
                        return 0;
                    };
                    return parseDate(a.data.data) - parseDate(b.data.data);
                });

                subNodes.push({
                    data: {
                        id: `sub_${monthId}_${catIndex}_${subIndex}`,
                        nome: subName,
                        valor: subVal.valor,
                        tipo: subVal.tipo,
                        consistente: subVal.consistente,
                        motivo_inconsistencia: subVal.motivo_inconsistencia,
                        nivel: 3
                    },
                    children: subVal.transactions
                });
                subIndex++;
            });

            catNodes.push({
                data: {
                    id: `cat_${monthId}_${catIndex}`,
                    nome: catName,
                    valor: catVal.valor,
                    tipo: catVal.tipo,
                    consistente: catVal.consistente,
                    motivo_inconsistencia: catVal.motivo_inconsistencia,
                    nivel: 2
                },
                expanded: true,
                children: subNodes
            });
            catIndex++;
        });

        return [
            {
                data: monthStats,
                children: catNodes,
                expanded: true
            }
        ];
    }

    ngOnInit() {
        this.detectEnvironmentAndLoad();
    }

    detectEnvironmentAndLoad() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            this.isMockMode = false;
            this.dbStatusText = 'Conectado';
            this.dbStatusSeverity = 'success';
            this.loadRealData();
        } else {
            // Se o pywebview.api não carregar imediatamente, espera 500ms caso seja inicialização lenta
            setTimeout(() => {
                const pywebviewRetry = (window as any).pywebview;
                if (pywebviewRetry && pywebviewRetry.api) {
                    this.isMockMode = false;
                    this.dbStatusText = 'Conectado';
                    this.dbStatusSeverity = 'success';
                    this.loadRealData();
                } else {
                    console.warn('API pywebview não detectada. Entrando em Modo Simulação (Mocks).');
                    this.isMockMode = true;
                    this.dbStatusText = 'Modo Simulação (Sem Conexão)';
                    this.dbStatusSeverity = 'warn';
                    this.loadMockData();
                }
            }, 500);
        }
    }

    testConnection() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            this.dbStatusText = 'Testando...';
            this.dbStatusSeverity = 'info';
            pywebview.api.test_db_connection()
                .then((res: any) => {
                    if (res.status === 'success') {
                        this.dbStatusText = 'Conectado com Sucesso';
                        this.dbStatusSeverity = 'success';
                        this.loadRealData();
                    } else {
                        this.dbStatusText = 'Erro de Conexão';
                        this.dbStatusSeverity = 'danger';
                        alert(res.message);
                    }
                })
                .catch((err: any) => {
                    this.dbStatusText = 'Erro de Comunicação';
                    this.dbStatusSeverity = 'danger';
                    alert('Erro ao se conectar ao backend: ' + err);
                });
        } else {
            alert('Não foi possível testar a conexão real: O sistema está rodando no navegador (Modo Simulação).');
        }
    }

    loadRealData() {
        const api = (window as any).pywebview.api;

        // 0. Carrega Informações do Condomínio
        api.get_condominio_info().then((res: any) => {
            if (res.status === 'success' && res.data) {
                this.layoutService.condominioNome.set(res.data.nome);
            }
        });

        // 1. Carrega Estatísticas
        api.get_dashboard_stats().then((res: any) => {
            if (res.status === 'success') {
                this.stats = res.stats;
            }
        });

        // 2. Carrega Meses
        api.get_all_months().then((res: any) => {
            if (res.status === 'success') {
                this.months = res.data;
                this.buildMonthFilterOptions();
                if (this.months.length > 0) {
                    this.selectMonthNode(this.months[0].id);
                }
            }
        });

        // 3. Carrega Lançamentos
        api.get_all_transactions().then((res: any) => {
            if (res.status === 'success') {
                this.transactions = res.data;
                this.applyFilters();
            }
        });
    }

    loadMockData() {
        this.layoutService.condominioNome.set('CONDOMÍNIO SAKAI MOCK');
        this.stats = {
            total_receitas: 245900.50,
            total_despesas: 210450.20,
            total_meses: 6,
            total_transacoes: 48,
            total_inconsistencias: 5,
            total_anexos: 32,
            total_prestacoes: 4
        };

        this.months = [
            { id: '202606', exibicao: 'Junho 2026', receita_total: 45000.0, despesa_total: 38200.0, consistente: 1, motivo_inconsistencia: null },
            { id: '202605', exibicao: 'Maio 2026', receita_total: 42000.0, despesa_total: 41200.0, consistente: 1, motivo_inconsistencia: null },
            { id: '202604', exibicao: 'Abril 2026', receita_total: 39500.0, despesa_total: 41000.0, consistente: 0, motivo_inconsistencia: '["Divergência em despesas"]' },
            { id: '202603', exibicao: 'Março 2026', receita_total: 41000.0, despesa_total: 35000.0, consistente: 1, motivo_inconsistencia: null },
            { id: '202602', exibicao: 'Fevereiro 2026', receita_total: 38400.0, despesa_total: 28050.20, consistente: 1, motivo_inconsistencia: null },
            { id: '202601', exibicao: 'Janeiro 2026', receita_total: 40000.50, despesa_total: 27000.0, consistente: 1, motivo_inconsistencia: null }
        ];

        this.transactions = [
            // Junho 2026 (202606) - receita 45000.0, despesa 38200.0
            { transacao_id: 101, tipo: 'R', data: '10/06/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 20000.0, apartamento: '101', competencia: '2026-06', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 102, tipo: 'R', data: '11/06/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 20000.0, apartamento: '102', competencia: '2026-06', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 103, tipo: 'R', data: '12/06/2026', descricao: 'Fundo de Reserva Apto 101', valor: 2500.0, apartamento: '101', competencia: '2026-06', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 104, tipo: 'R', data: '12/06/2026', descricao: 'Fundo de Reserva Apto 102', valor: 2500.0, apartamento: '102', competencia: '2026-06', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 105, tipo: 'D', data: '05/06/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 106, tipo: 'D', data: '15/06/2026', descricao: 'Pagamento Elevadores S/A - Manutenção Mensal', valor: 38000.0, apartamento: null, competencia: null, fornecedor: 'Elevadores S/A', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Manutenção de Elevadores', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Junho 2026', mes_id: '202606' },

            // Maio 2026 (202605) - receita 42000.0, despesa 41200.0
            { transacao_id: 201, tipo: 'R', data: '10/05/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 19000.0, apartamento: '101', competencia: '2026-05', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 202, tipo: 'R', data: '11/05/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 19000.0, apartamento: '102', competencia: '2026-05', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 203, tipo: 'R', data: '12/05/2026', descricao: 'Fundo de Reserva Apto 101', valor: 2000.0, apartamento: '101', competencia: '2026-05', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 204, tipo: 'R', data: '12/05/2026', descricao: 'Fundo de Reserva Apto 102', valor: 2000.0, apartamento: '102', competencia: '2026-05', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 205, tipo: 'D', data: '05/05/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 206, tipo: 'D', data: '15/05/2026', descricao: 'Pagamento Elevadores S/A - Manutenção Mensal', valor: 38000.0, apartamento: null, competencia: null, fornecedor: 'Elevadores S/A', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Manutenção de Elevadores', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 207, tipo: 'D', data: '20/05/2026', descricao: 'Consumo de Água Copasa', valor: 3000.0, apartamento: null, competencia: null, fornecedor: 'COPASA', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Água e Esgoto', categoria_nome: 'DESPESAS CONSUMO', mes_exibicao: 'Maio 2026', mes_id: '202605' },

            // Abril 2026 (202604) - receita 39500.0, despesa 41000.0 (consistente: 0)
            { transacao_id: 301, tipo: 'R', data: '10/04/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 18000.0, apartamento: '101', competencia: '2026-04', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 302, tipo: 'R', data: '11/04/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 18000.0, apartamento: '102', competencia: '2026-04', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 303, tipo: 'R', data: '12/04/2026', descricao: 'Fundo de Reserva Apto 101', valor: 1750.0, apartamento: '101', competencia: '2026-04', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 304, tipo: 'R', data: '12/04/2026', descricao: 'Fundo de Reserva Apto 102', valor: 1750.0, apartamento: '102', competencia: '2026-04', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 305, tipo: 'D', data: '05/04/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 306, tipo: 'D', data: '15/04/2026', descricao: 'Pagamento Elevadores S/A - Manutenção Mensal', valor: 38000.0, apartamento: null, competencia: null, fornecedor: 'Elevadores S/A', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Manutenção de Elevadores', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },
            { transacao_id: 307, tipo: 'D', data: '22/04/2026', descricao: 'Pagamento Seguro Predial SulAmerica NF: 122', valor: 3200.0, apartamento: null, competencia: null, fornecedor: 'SULAMERICA', qtde_anexos_original: 0, consistente: 0, motivo_inconsistencia: '["Quantidade de anexos divergente"]', subcategoria_nome: 'Seguros', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Abril 2026', mes_id: '202604' },

            // Março 2026 (202603) - receita 41000.0, despesa 35000.0
            { transacao_id: 401, tipo: 'R', data: '10/03/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 19000.0, apartamento: '101', competencia: '2026-03', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Março 2026', mes_id: '202603' },
            { transacao_id: 402, tipo: 'R', data: '11/03/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 19000.0, apartamento: '102', competencia: '2026-03', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Março 2026', mes_id: '202603' },
            { transacao_id: 403, tipo: 'R', data: '12/03/2026', descricao: 'Fundo de Reserva Apto 101', valor: 1500.0, apartamento: '101', competencia: '2026-03', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Março 2026', mes_id: '202603' },
            { transacao_id: 404, tipo: 'R', data: '12/03/2026', descricao: 'Fundo de Reserva Apto 102', valor: 1500.0, apartamento: '102', competencia: '2026-03', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Março 2026', mes_id: '202603' },
            { transacao_id: 405, tipo: 'D', data: '05/03/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Março 2026', mes_id: '202603' },
            { transacao_id: 406, tipo: 'D', data: '15/03/2026', descricao: 'Pagamento Terceirização Limpeza', valor: 34800.0, apartamento: null, competencia: null, fornecedor: 'Limpeza S/A', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Terceirização', categoria_nome: 'DESPESAS OPERACIONAIS', mes_exibicao: 'Março 2026', mes_id: '202603' },

            // Fevereiro 2026 (202602) - receita 38400.0, despesa 28050.20
            { transacao_id: 501, tipo: 'R', data: '10/02/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 18000.0, apartamento: '101', competencia: '2026-02', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 502, tipo: 'R', data: '11/02/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 18000.0, apartamento: '102', competencia: '2026-02', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 503, tipo: 'R', data: '12/02/2026', descricao: 'Fundo de Reserva Apto 101', valor: 1200.0, apartamento: '101', competencia: '2026-02', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 504, tipo: 'R', data: '12/02/2026', descricao: 'Fundo de Reserva Apto 102', valor: 1200.0, apartamento: '102', competencia: '2026-02', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 505, tipo: 'D', data: '05/02/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 506, tipo: 'D', data: '12/02/2026', descricao: 'Pagamento Energia Cemig', valor: 1450.20, apartamento: null, competencia: null, fornecedor: 'CEMIG', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Energia Elétrica', categoria_nome: 'DESPESAS CONSUMO', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },
            { transacao_id: 507, tipo: 'D', data: '18/02/2026', descricao: 'Manutenção Portão Garagem', valor: 26400.0, apartamento: null, competencia: null, fornecedor: 'Portões BH', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Manutenção Geral', categoria_nome: 'DESPESAS OPERACIONAIS', mes_exibicao: 'Fevereiro 2026', mes_id: '202602' },

            // Janeiro 2026 (202601) - receita 40000.50, despesa 27000.0
            { transacao_id: 601, tipo: 'R', data: '10/01/2026', descricao: 'Recebimento Taxa Ordinária Apto 101', valor: 18500.0, apartamento: '101', competencia: '2026-01', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 602, tipo: 'R', data: '11/01/2026', descricao: 'Recebimento Taxa Ordinária Apto 102', valor: 18500.0, apartamento: '102', competencia: '2026-01', fornecedor: null, qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 603, tipo: 'R', data: '12/01/2026', descricao: 'Fundo de Reserva Apto 101', valor: 1500.0, apartamento: '101', competencia: '2026-01', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 604, tipo: 'R', data: '12/01/2026', descricao: 'Fundo de Reserva Apto 102', valor: 1500.0, apartamento: '102', competencia: '2026-01', fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Fundo de Reserva', categoria_nome: 'RECEITAS ORDINÁRIAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 605, tipo: 'R', data: '20/01/2026', descricao: 'Rendimento RDB Sicoob', valor: 0.50, apartamento: null, competencia: null, fornecedor: null, qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Rendimentos', categoria_nome: 'RECEITAS DIVERSAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 606, tipo: 'D', data: '05/01/2026', descricao: 'Tarifa Mensal Cobrança - SICOOB', valor: 200.0, apartamento: null, competencia: null, fornecedor: 'SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' },
            { transacao_id: 607, tipo: 'D', data: '15/01/2026', descricao: 'Pagamento Assessoria Contábil', valor: 26800.0, apartamento: null, competencia: null, fornecedor: 'Assessoria Contábil', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Assessoria', categoria_nome: 'DESPESAS ADMINISTRATIVAS', mes_exibicao: 'Janeiro 2026', mes_id: '202601' }
        ];

        this.buildMonthFilterOptions();
        this.applyFilters();
        if (this.months.length > 0) {
            this.selectMonthNode(this.months[0].id);
        }
    }

    buildMonthFilterOptions() {
        this.filterMonthOptions = [{ label: 'Todos', value: null }];
        const mapped = this.months.map(m => ({ label: m.exibicao, value: m.id }));
        this.filterMonthOptions.push(...mapped);
    }

    applyFilters() {
        const query = this.searchQuery.toLowerCase().trim();
        this.filteredTransactions = this.transactions.filter(t => {
            // Filtro de Busca Textual
            const matchesQuery = !query || 
                t.descricao.toLowerCase().includes(query) || 
                (t.fornecedor && t.fornecedor.toLowerCase().includes(query)) ||
                (t.conta && t.conta.toLowerCase().includes(query)) ||
                t.subcategoria_nome.toLowerCase().includes(query) ||
                t.categoria_nome.toLowerCase().includes(query);

            // Filtro de Competência (Mês)
            const matchesMonth = !this.selectedMonth || t.mes_id === this.selectedMonth;

            // Filtro de Tipo (R/D)
            const matchesType = !this.selectedType || t.tipo === this.selectedType;

            // Filtro de Consistência (1/0)
            const matchesConsistency = this.selectedConsistency === null || t.consistente === this.selectedConsistency;

            return matchesQuery && matchesMonth && matchesType && matchesConsistency;
        });
    }

    resetFilters() {
        this.searchQuery = '';
        this.selectedMonth = null;
        this.selectedType = null;
        this.selectedConsistency = null;
        this.applyFilters();
    }

    formatComp(comp: string | null): string {
        if (!comp) return '';
        // Converte YYYY-MM para MM/YYYY
        const parts = comp.split('-');
        if (parts.length === 2) {
            return `${parts[1]}/${parts[0]}`;
        }
        return comp;
    }

    formatReasons(reasonsStr: string | null): string {
        if (!reasonsStr) return 'Dados inconsistentes';
        try {
            const reasons = JSON.parse(reasonsStr);
            if (Array.isArray(reasons)) {
                return reasons.join(' | ');
            }
            return reasonsStr;
        } catch {
            return reasonsStr;
        }
    }
}
