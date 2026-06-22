import { Component, OnInit } from '@angular/core';
import { CommonModule, registerLocaleData } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { TagModule } from 'primeng/tag';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { TooltipModule } from 'primeng/tooltip';
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
    conta: string | null;
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
        TooltipModule
    ],
    templateUrl: './dashboard.html'
})
export class Dashboard implements OnInit {
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
            { transacao_id: 1, tipo: 'R', data: '10/06/2026', descricao: 'Taxa Ordinária Apto 101', valor: 450.0, apartamento: '101', competencia: '2026-06', fornecedor: null, conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'Receitas Taxas', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 2, tipo: 'R', data: '10/06/2026', descricao: 'Taxa Ordinária Apto 202', valor: 450.0, apartamento: '202', competencia: '2026-06', fornecedor: null, conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Taxa Ordinária', categoria_nome: 'Receitas Taxas', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 3, tipo: 'D', data: '12/06/2026', descricao: 'Pagamento Cemig Distribuição - Conta Energia', valor: 1450.20, apartamento: null, competencia: null, fornecedor: 'CEMIG', conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 1, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Energia Elétrica', categoria_nome: 'Despesas Consumo', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 4, tipo: 'D', data: '15/06/2026', descricao: 'Tarifa Mensal Cobrança', valor: 69.50, apartamento: null, competencia: null, fornecedor: 'SICOOB', conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 0, consistente: 1, motivo_inconsistencia: null, subcategoria_nome: 'Tarifas Bancárias', categoria_nome: 'Despesas Administrativas', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 5, tipo: 'R', data: '22/06/2026', descricao: 'Rendimento de Aplicação RDB', valor: 312.45, apartamento: null, competencia: null, fornecedor: null, conta: 'CONTA INVESTIMENTO - SICOOB', qtde_anexos_original: 0, consistente: 0, motivo_inconsistencia: '["Apartamento não identificado", "Competência não identificada"]', subcategoria_nome: 'Rendimento de Aplicação', categoria_nome: 'Receitas Diversas', mes_exibicao: 'Junho 2026', mes_id: '202606' },
            { transacao_id: 6, tipo: 'D', data: '10/05/2026', descricao: 'Pagamento Limpeza S/A', valor: 1200.0, apartamento: null, competencia: null, fornecedor: null, conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 1, consistente: 0, motivo_inconsistencia: '["Fornecedor não identificado"]', subcategoria_nome: 'Terceirização', categoria_nome: 'Despesas Operacionais', mes_exibicao: 'Maio 2026', mes_id: '202605' },
            { transacao_id: 7, tipo: 'D', data: '11/04/2026', descricao: 'Pagamento Seguro Predial SulAmerica NF: 122', valor: 3200.0, apartamento: null, competencia: null, fornecedor: 'SULAMERICA', conta: 'CONTA CORRENTE - SICOOB', qtde_anexos_original: 0, consistente: 0, motivo_inconsistencia: '["Quantidade de anexos divergente"]', subcategoria_nome: 'Seguros', categoria_nome: 'Despesas Administrativas', mes_exibicao: 'Abril 2026', mes_id: '202604' }
        ];

        this.buildMonthFilterOptions();
        this.applyFilters();
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
