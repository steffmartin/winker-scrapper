import { Component, OnInit, ChangeDetectorRef, LOCALE_ID, inject } from '@angular/core';
import { CommonModule, CurrencyPipe, DatePipe, registerLocaleData } from '@angular/common';
import { SkeletonModule } from 'primeng/skeleton';
import { ChipModule } from 'primeng/chip';
import { TreeTableModule } from 'primeng/treetable';
import { DatePickerModule } from 'primeng/datepicker';
import { ToolbarModule } from 'primeng/toolbar';
import { ButtonModule } from 'primeng/button';
import { ButtonGroupModule } from 'primeng/buttongroup';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { FormsModule } from '@angular/forms';
import { TreeNode } from 'primeng/api';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { InputGroupModule } from 'primeng/inputgroup';
import { InputGroupAddonModule } from 'primeng/inputgroupaddon';
import { ChartModule } from 'primeng/chart';
import localePt from '@angular/common/locales/pt';

registerLocaleData(localePt);

import { LayoutService } from '@/app/layout/service/layout.service';

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [
        CommonModule,
        CurrencyPipe,
        SkeletonModule,
        ChipModule,
        TreeTableModule,
        DatePickerModule,
        ToolbarModule,
        ButtonModule,
        ButtonGroupModule,
        TagModule,
        TooltipModule,
        FormsModule,
        IconFieldModule,
        InputIconModule,
        InputTextModule,
        InputGroupModule,
        InputGroupAddonModule,
        ChartModule
    ],
    providers: [
        { provide: LOCALE_ID, useValue: 'pt-BR' }
    ],
    templateUrl: './dashboard.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown {
            background-color: var(--p-primary-color, var(--primary-color)) !important;
            border-color: var(--p-primary-color, var(--primary-color)) !important;
            color: var(--p-primary-contrast-color, var(--primary-color-text)) !important;
        }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown:hover {
            background-color: var(--p-primary-hover-color, var(--primary-600)) !important;
            border-color: var(--p-primary-hover-color, var(--primary-600)) !important;
        }
    `]
})
export class Dashboard implements OnInit {
    isMockMode = false;
    loadingKpis = true;
    kpis: any = {
        inadimplencia: null,
        gestao: null,
        saldos: null,
        resumo_mes: null,
        estatisticas: null
    };

    sindicoName = 'Sem Síndico';
    conselheirosList: string[] = [];

    layoutService = inject(LayoutService);

    // TreeTable State
    nodes: TreeNode[] = [];
    loadingTreeTable = true;
    dateRange: Date[] = [];
    globalFilterValue = '';
    maxDate = new Date(new Date().setHours(23, 59, 59, 999));

    // Chart State
    chartData: any;
    chartOptions: any;
    isSingleMonth = false;

    constructor(private cdr: ChangeDetectorRef) {}

    ngOnInit() {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
        this.dateRange = [firstDay, today];

        this.detectEnvironmentAndLoad();

        // Listen to theme changes to update chart colors
        if ((this.layoutService as any).configUpdate$) {
            (this.layoutService as any).configUpdate$.subscribe(() => {
                this.initChartOptions();
                this.cdr.detectChanges();
            });
        }
    }

    detectEnvironmentAndLoad() {
        if ((window as any).pywebview && (window as any).pywebview.api) {
            this.isMockMode = false;
            this.fetchKpis((window as any).pywebview.api);
            this.fetchTransacoes((window as any).pywebview.api);
        } else {
            // Wait for the pywebviewready event
            window.addEventListener('pywebviewready', () => {
                this.isMockMode = false;
                this.fetchKpis((window as any).pywebview.api);
                this.fetchTransacoes((window as any).pywebview.api);
            });

            // Fallback for local development (ng serve)
            setTimeout(() => {
                if (this.loadingKpis || this.loadingTreeTable) {
                    if ((window as any).pywebview && (window as any).pywebview.api) {
                        this.isMockMode = false;
                        this.fetchKpis((window as any).pywebview.api);
                        this.fetchTransacoes((window as any).pywebview.api);
                    } else if (window.location.hostname === 'localhost') {
                        console.warn('Rodando localmente (ng serve). Entrando em Modo Simulação (Mocks).');
                        this.isMockMode = true;
                        this.loadMockKpis();
                        this.loadMockTransacoes();
                    } else {
                        // Se não for localhost, espera mais tempo pelo pywebview
                        console.warn('Aguardando PyWebView carregar...');
                        setTimeout(() => {
                            if (this.loadingKpis) {
                                console.error('PyWebView falhou em carregar após 6 segundos. Mantendo interface em loading.');
                            }
                        }, 5000);
                    }
                }
            }, 1000);
        }
    }

    fetchKpis(api: any) {
        api.get_dashboard_kpis().then((response: any) => {
            if (response.status === 'success') {
                this.kpis = response.data;
                this.processMembers();
            } else {
                console.error('Erro ao buscar KPIs', response.message);
            }
            this.loadingKpis = false;
            this.cdr.detectChanges();
        }).catch((err: any) => {
            console.error('Erro na chamada da API', err);
            this.loadingKpis = false;
            this.cdr.detectChanges();
        });
    }

    processMembers() {
        const membros = this.kpis?.gestao?.membros || [];

        const sindico = membros.find((m: any) => m.cargo && m.cargo.toLowerCase().includes('síndico') && !m.cargo.toLowerCase().includes('sub'));
        if (sindico) {
            this.sindicoName = sindico.nome;
        } else if (membros.length > 0) {
            this.sindicoName = membros[0].nome;
        }

        const conselheiros = membros.filter((m: any) => m.cargo && m.cargo.toLowerCase().includes('conselh'));
        if (conselheiros.length > 0) {
            this.conselheirosList = conselheiros.map((c: any) => {
                const parts = c.nome.trim().split(' ');
                return parts[0];
            });
        } else {
            this.conselheirosList = [];
        }
    }

    loadMockKpis() {
        this.kpis = {
            inadimplencia: {
                valor: 2500.50,
                unidades: 3,
                data_corte: '2023-10-01'
            },
            gestao: {
                membros: [
                    { nome: 'Carlos Silva', cargo: 'Síndico' },
                    { nome: 'Ana Souza', cargo: 'Conselheiro' },
                    { nome: 'Pedro Álvares', cargo: 'Conselheiro' }
                ],
                administradora: {
                    nome: 'Admin Teste LTDA',
                    telefone: '(11) 9999-9999'
                }
            },
            saldos: {
                saldo_total: 0,
                contas: [
                    { nome: 'Conta Corrente Padrão', saldo: 0 },
                    { nome: 'Fundo de Reserva', saldo: 0 }
                ]
            },
            resumo_mes: {
                competencia: '10/2023',
                receita_total: 30000.00,
                despesa_total: 28000.00,
                resultado: 2000.00
            }
        };
        this.processMembers();
        this.loadingKpis = false;
        this.cdr.detectChanges();
    }



    onDateRangeChange() {
        if (this.dateRange && this.dateRange.length === 2 && this.dateRange[0] && this.dateRange[1]) {
            this.loadingTreeTable = true;
            if (this.isMockMode) {
                this.loadMockTransacoes();
            } else if ((window as any).pywebview && (window as any).pywebview.api) {
                this.fetchTransacoes((window as any).pywebview.api);
            }
        }
    }

    setMesAtual(dp?: any) {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
        this.dateRange = [firstDay, today];
        this.dateRange = [...this.dateRange]; // Força o Angular a detectar a mudança do array
        this.onDateRangeChange();
        if (dp && dp.hide) dp.hide();
    }

    setAnoAtual(dp?: any) {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), 0, 1);
        this.dateRange = [firstDay, today];
        this.dateRange = [...this.dateRange]; // Força o Angular a detectar a mudança do array
        this.onDateRangeChange();
        if (dp && dp.hide) dp.hide();
    }

    fetchTransacoes(api: any) {
        let startStr = null;
        let endStr = null;

        if (this.dateRange && this.dateRange.length === 2 && this.dateRange[0] && this.dateRange[1]) {
            const tz1 = this.dateRange[0].getTimezoneOffset() * 60000;
            const tz2 = this.dateRange[1].getTimezoneOffset() * 60000;
            startStr = new Date(this.dateRange[0].getTime() - tz1).toISOString().split('T')[0];
            endStr = new Date(this.dateRange[1].getTime() - tz2).toISOString().split('T')[0];
        }

        api.get_transacoes(startStr, endStr).then((response: any) => {
            if (response.status === 'success') {
                this.nodes = this.processNodes(response.data);
                if (this.nodes.length === 1) {
                    this.expandLevels(2);
                } else if (this.nodes.length > 1) {
                    this.expandLevels(1);
                }
                this.updateChart(this.nodes);
            } else {
                console.error('Erro ao buscar transacoes', response.message);
                this.nodes = [];
            }
            this.loadingTreeTable = false;
            this.cdr.detectChanges();
        }).catch((err: any) => {
            console.error('Erro na chamada da API get_transacoes', err);
            this.loadingTreeTable = false;
            this.cdr.detectChanges();
        });
    }

    processNodes(nodes: TreeNode[], parentGrupo: string = ''): TreeNode[] {
        return nodes.map(node => {
            let grupo = parentGrupo;
            if (node.data.tipo_node === 'tipo') {
                grupo = node.data.descricao; // 'Receitas' ou 'Despesas'
            }
            node.data.grupo = grupo;

            if (node.children) {
                node.children = this.processNodes(node.children, grupo);
            }
            return node;
        });
    }

    expandAll() {
        let currentLevel = this.nodes;
        while (currentLevel.length > 0) {
            const hasCollapsed = currentLevel.some(n => n.children && n.children.length > 0 && !n.expanded);
            if (hasCollapsed) {
                currentLevel.forEach(n => {
                    if (n.children && n.children.length > 0) {
                        n.expanded = true;
                    }
                });
                break;
            }
            let nextLevel: TreeNode[] = [];
            currentLevel.forEach(n => {
                if (n.children && n.expanded) {
                    nextLevel.push(...n.children);
                }
            });
            currentLevel = nextLevel;
        }
        this.nodes = [...this.nodes];
    }

    expandLevels(levelsToExpand: number) {
        let currentLevel = this.nodes;
        for (let i = 0; i < levelsToExpand; i++) {
            let nextLevel: TreeNode[] = [];
            currentLevel.forEach(n => {
                if (n.children && n.children.length > 0) {
                    n.expanded = true;
                    nextLevel.push(...n.children);
                }
            });
            currentLevel = nextLevel;
        }
    }

    applyGlobalFilter(tt: any) {
        const val = this.globalFilterValue;
        if (val && val.trim().length > 0) {
            this.nodes.forEach(node => {
                this.expandRecursive(node, true);
            });
            this.nodes = [...this.nodes];
            tt.filterGlobal(val, 'contains');
            setTimeout(() => this.updateChart(tt.filteredNodes || this.nodes));
        } else {
            tt.filterGlobal('', 'contains');
            setTimeout(() => this.updateChart(this.nodes));
        }
    }

    clearFilter(tt: any) {
        this.globalFilterValue = '';
        this.applyGlobalFilter(tt);
    }

    collapseAll() {
        let levels: TreeNode[][] = [this.nodes];
        let currentLevel = this.nodes;

        while (currentLevel.length > 0) {
            let nextLevel: TreeNode[] = [];
            currentLevel.forEach(n => {
                if (n.children && n.expanded) {
                    nextLevel.push(...n.children);
                }
            });
            if (nextLevel.length > 0) {
                levels.push(nextLevel);
            }
            currentLevel = nextLevel;
        }

        if (levels.length > 1) {
            const levelToCollapse = levels[levels.length - 2];
            levelToCollapse.forEach(n => {
                n.expanded = false;
            });
        }
        this.nodes = [...this.nodes];
    }

    private expandRecursive(node: TreeNode, isExpand: boolean) {
        node.expanded = isExpand;
        if (node.children) {
            node.children.forEach(childNode => {
                this.expandRecursive(childNode, isExpand);
            });
        }
    }

    getRowClass(rowData: any) {
        if (!rowData) return '';
        const t = rowData.tipo_node;
        const g = rowData.grupo;
        if (t === 'mes') return '[&>td]:!bg-primary-100 dark:[&>td]:!bg-primary-900/40 [&>td]:!text-primary-900 dark:[&>td]:!text-primary-100 font-bold [&>td]:!shadow-[inset_0_10px_0_0_var(--surface-card)] [&>td]:!pt-5';

        if (g === 'Despesas') {
            switch(t) {
                case 'tipo': return '[&>td]:!bg-red-200/50 dark:[&>td]:!bg-red-900/40 text-red-900 dark:text-red-100 font-semibold';
                case 'categoria': return '[&>td]:!bg-red-100/50 dark:[&>td]:!bg-red-900/30 text-red-800 dark:text-red-200';
                case 'subcategoria': return '[&>td]:!bg-red-50/50 dark:[&>td]:!bg-red-900/20 text-red-700 dark:text-red-300';
                case 'transacao': return '[&>td]:!bg-white/50 dark:[&>td]:!bg-red-900/10 text-slate-600 dark:text-slate-400 text-sm';
            }
        } else if (g === 'Receitas') {
            switch(t) {
                case 'tipo': return '[&>td]:!bg-green-200/50 dark:[&>td]:!bg-green-900/40 text-green-900 dark:text-green-100 font-semibold';
                case 'categoria': return '[&>td]:!bg-green-100/50 dark:[&>td]:!bg-green-900/30 text-green-800 dark:text-green-200';
                case 'subcategoria': return '[&>td]:!bg-green-50/50 dark:[&>td]:!bg-green-900/20 text-green-700 dark:text-green-300';
                case 'transacao': return '[&>td]:!bg-white/50 dark:[&>td]:!bg-green-900/10 text-slate-600 dark:text-slate-400 text-sm';
            }
        }
        return '';
    }

    loadMockTransacoes() {
        setTimeout(() => {
            this.nodes = [
                {
                    data: { descricao: 'Junho/2026', valor_total: 3500, tipo_node: 'mes' },
                    expanded: true,
                    children: [
                        {
                            data: { descricao: 'Receitas', valor_total: 2000, porcentagem: 57.14, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Taxa Condominial', valor_total: 2000, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: true,
                                    children: [
                                        {
                                            data: { descricao: 'Cotas Ordinárias', valor_total: 2000, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                            expanded: true,
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Boleto',
                                                        fornecedor: '-',
                                                        apartamento: '101',
                                                        competencia: '06/2026',
                                                        valor: 1200,
                                                        data: '2026-06-05',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 1
                                                    }
                                                },
                                                {
                                                    data: {
                                                        descricao: 'Boleto',
                                                        fornecedor: '-',
                                                        apartamento: '102',
                                                        competencia: '06/2026',
                                                        valor: 800,
                                                        data: '2026-06-07',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 0
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            data: { descricao: 'Despesas', valor_total: 1500, porcentagem: 42.86, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Despesas Ordinárias', valor_total: 1500, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: true,
                                    children: [
                                        {
                                            data: { descricao: 'Limpeza', valor_total: 1500, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                    expanded: true,
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Compra de produtos',
                                                        fornecedor: 'Mercado X',
                                                        apartamento: 'Condomínio',
                                                        competencia: '06/2026',
                                                        valor: 1500,
                                                        data: '2026-06-15',
                                                        revisado: false,
                                                        tipo_node: 'transacao',
                                                        anexos: 2
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    data: { descricao: 'Maio/2026', valor_total: 1000, tipo_node: 'mes' },
                    expanded: false,
                    children: [
                        {
                            data: { descricao: 'Despesas', valor_total: 1000, porcentagem: 100.0, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Despesas Ordinárias', valor_total: 1000, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: false,
                                    children: [
                                        {
                                            data: { descricao: 'Manutenção', valor_total: 1000, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Conserto Elevador',
                                                        fornecedor: 'Elevadores SA',
                                                        apartamento: '-',
                                                        competencia: '05/2026',
                                                        valor: 1000,
                                                        data: '2026-05-20',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 1
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ];
            this.nodes = this.processNodes(this.nodes);
            this.updateChart(this.nodes);
            this.loadingTreeTable = false;
            this.cdr.detectChanges();
        }, 800);
    }

    updateChart(nodes: TreeNode[]) {
        let allLeaves: any[] = [];

        const traverse = (node: TreeNode, context: any) => {
            const newContext = { ...context };
            if (node.data.tipo_node === 'mes') newContext.mes = node.data.descricao;
            if (node.data.tipo_node === 'categoria') newContext.categoria = node.data.descricao;
            if (node.data.grupo) newContext.grupo = node.data.grupo;

            if (node.data.tipo_node === 'transacao') {
                allLeaves.push({
                    leaf: node.data,
                    mes: newContext.mes,
                    categoria: newContext.categoria,
                    grupo: newContext.grupo
                });
            }
            if (node.children) {
                node.children.forEach(child => traverse(child, newContext));
            }
        };
        (nodes || []).forEach(n => traverse(n, {}));

        const mesesSet = new Set<string>();
        allLeaves.forEach(item => mesesSet.add(item.mes));

        // A ordem dos meses já vem corretamente ordenada (crescente) do backend
        const mesesArr = Array.from(mesesSet);

        this.isSingleMonth = mesesArr.length <= 1;

        if (this.isSingleMonth) {
            // Stacked Bar Chart by Categoria
            const categoriasSet = new Set<string>();
            const catGrupoMap = new Map<string, string>();

            allLeaves.forEach(item => {
                categoriasSet.add(item.categoria);
                catGrupoMap.set(item.categoria, item.grupo);
            });
            const categoriasArr = Array.from(categoriasSet);

            const datasets = categoriasArr.map((cat, index) => {
                const grupo = catGrupoMap.get(cat);
                const color = this.getCategoryColor(index, grupo || 'Receitas');
                let receitaSum = 0;
                let despesaSum = 0;

                allLeaves.filter(i => i.categoria === cat).forEach(item => {
                    if (item.grupo === 'Receitas') receitaSum += (item.leaf.valor || 0);
                    if (item.grupo === 'Despesas') despesaSum += (item.leaf.valor || 0);
                });

                return {
                    label: cat,
                    data: [receitaSum, despesaSum],
                    backgroundColor: color,
                };
            });

            this.chartData = {
                labels: ['Receitas', 'Despesas'],
                datasets: datasets
            };
        } else {
            // Line chart for multiple months
            const receitasData = mesesArr.map(mes => {
                let sum = 0;
                allLeaves.filter(i => i.mes === mes && i.grupo === 'Receitas').forEach(i => sum += (i.leaf.valor || 0));
                return sum;
            });
            const despesasData = mesesArr.map(mes => {
                let sum = 0;
                allLeaves.filter(i => i.mes === mes && i.grupo === 'Despesas').forEach(i => sum += (i.leaf.valor || 0));
                return sum;
            });

            const documentStyle = getComputedStyle(document.documentElement);
            this.chartData = {
                labels: mesesArr,
                datasets: [
                    {
                        label: 'Receitas',
                        data: receitasData,
                        fill: false,
                        borderColor: documentStyle.getPropertyValue('--p-green-500') || '#22c55e',
                        tension: 0.4
                    },
                    {
                        label: 'Despesas',
                        data: despesasData,
                        fill: false,
                        borderColor: documentStyle.getPropertyValue('--p-red-500') || '#ef4444',
                        tension: 0.4
                    }
                ]
            };
        }

        this.initChartOptions();
        this.cdr.detectChanges();
    }

    getCategoryColor(index: number, grupo: string) {
        // Colors from Tailwind green/red scale
        const receitasColors = ['#10b981', '#34d399', '#059669', '#047857', '#6ee7b7'];
        const despesasColors = ['#ef4444', '#f87171', '#dc2626', '#b91c1c', '#fca5a5', '#f97316', '#fb923c'];

        if (grupo === 'Receitas') return receitasColors[index % receitasColors.length];
        return despesasColors[index % despesasColors.length];
    }

    initChartOptions() {
        const documentStyle = getComputedStyle(document.documentElement);
        const textColor = documentStyle.getPropertyValue('--text-color') || '#495057';
        const textColorSecondary = documentStyle.getPropertyValue('--text-color-secondary') || '#6c757d';
        const surfaceBorder = documentStyle.getPropertyValue('--surface-border') || '#dfe7ef';

        this.chartOptions = {
            maintainAspectRatio: false,
            aspectRatio: 0.8,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context: any) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: this.isSingleMonth,
                    ticks: {
                        color: textColorSecondary,
                        font: {
                            weight: 500
                        }
                    },
                    grid: {
                        color: surfaceBorder,
                        drawBorder: false
                    }
                },
                y: {
                    stacked: this.isSingleMonth,
                    ticks: {
                        color: textColorSecondary,
                        callback: function(value: any) {
                            return 'R$ ' + value;
                        }
                    },
                    grid: {
                        color: surfaceBorder,
                        drawBorder: false
                    }
                }
            }
        };
    }
}
