import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Dashboard } from './dashboard';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

describe('Dashboard', () => {
    let component: Dashboard;
    let fixture: ComponentFixture<Dashboard>;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [Dashboard, CommonModule],
            providers: [
                {
                    provide: ActivatedRoute,
                    useValue: {
                        snapshot: { paramMap: { get: () => null } }
                    }
                }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(Dashboard);
        component = fixture.componentInstance;
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('marca todas as viradas de ano mesmo sem janeiro e no último ponto', () => {
        component.initChartPlugins();
        const ctx = { save: jasmine.createSpy(), beginPath: jasmine.createSpy(), setLineDash: jasmine.createSpy(),
            moveTo: jasmine.createSpy(), lineTo: jasmine.createSpy(), stroke: jasmine.createSpy(),
            fillText: jasmine.createSpy(), restore: jasmine.createSpy() };
        const labels = ['ABR/2022', 'DEZ/2022', 'FEV/2023', 'DEZ/2023', 'JAN/2024', 'JAN/2025', 'JAN/2026'];
        const chart = { ctx, chartArea: { top: 0, bottom: 100 }, data: { labels },
            scales: { x: { getPixelForValue: (i: number) => i * 10 } },
            getDatasetMeta: () => ({ data: labels.map((_, i) => ({ x: i * 10 })) }) };
        component.chartPlugins[0].afterDraw(chart);
        expect(ctx.fillText.calls.allArgs().map(args => args[0])).toEqual(['2023', '2024', '2025', '2026']);
        expect(ctx.moveTo.calls.allArgs().map(args => args[0])).toEqual([15, 40, 50, 60]);
    });

    it('restringe toda a árvore por apartamento, inclusive números com zeros à esquerda', () => {
        const folha = (apartamento: any, valor: number) => ({ data: { tipo_node: 'transacao', apartamento, valor } });
        const mes = (descricao: string, folhas: any[]) => ({ data: { tipo_node: 'mes', descricao }, children: [
            { data: { tipo_node: 'tipo', descricao: 'Receitas' }, children: [
                { data: { tipo_node: 'categoria', descricao: 'Taxas' }, children: [
                    { data: { tipo_node: 'subcategoria', descricao: 'Taxas' }, children: folhas }
                ] }
            ] }
        ] });
        component.nodes = component.processNodes([mes('JAN/2024', [folha('0101', 10), folha('102', 20)]), mes('FEV/2024', [folha(101, 30)])]);
        component.globalFilterValue = '101';
        const tabela = { reset: jasmine.createSpy(), filterGlobal: jasmine.createSpy() };
        component.applyGlobalFilter(tabela);
        expect(component.nodesExibidos.length).toBe(2);
        const primeiro = component.nodesExibidos[0].children![0].children![0].children![0];
        expect(primeiro.children!.map(n => n.data.apartamento)).toEqual(['0101']);
        expect(component.nodesExibidos[0].data.valor_total).toBe(10);
        expect(component.chartData.labels).toEqual(['JAN/2024', 'FEV/2024']);
        component.globalFilterValue = '999';
        component.applyGlobalFilter(tabela);
        expect(component.nodesExibidos).toEqual([]);
        component.clearFilter(tabela);
        expect(component.nodesExibidos).toBe(component.nodes);
    });

    it('recalcula totais e gráfico ao filtrar uma transação por texto e restaura ao limpar', () => {
        const transacoes = [{ data: { tipo_node: 'transacao', descricao: 'Água janeiro', valor: 10 } },
            { data: { tipo_node: 'transacao', descricao: 'Luz janeiro', valor: 20 } }];
        component.nodes = component.processNodes([{ data: { tipo_node: 'mes', descricao: 'JAN/2024', valor_total: 30 }, children: [
            { data: { tipo_node: 'tipo', descricao: 'Despesas', valor_total: 30 }, children: [
                { data: { tipo_node: 'categoria', descricao: 'Serviços', valor_total: 30 }, children: [
                    { data: { tipo_node: 'subcategoria', descricao: 'Consumo', valor_total: 30 }, children: transacoes }
                ] }
            ] }
        ] }]);
        const tabela = { reset: jasmine.createSpy(), filterGlobal: jasmine.createSpy() };
        component.globalFilterValue = 'agua';
        component.applyGlobalFilter(tabela);
        const mes = component.nodesExibidos[0];
        const tipo = mes.children![0];
        const categoria = tipo.children![0];
        const subcategoria = categoria.children![0];
        expect([mes.data.valor_total, tipo.data.valor_total, categoria.data.valor_total, subcategoria.data.valor_total]).toEqual([10, 10, 10, 10]);
        expect(subcategoria.children!.map(n => n.data.descricao)).toEqual(['Água janeiro']);
        expect(component.chartData.datasets[0].data).toEqual([0, 10]);
        expect(component.nodes[0].data.valor_total).toBe(30);
        component.globalFilterValue = 'servicos';
        component.applyGlobalFilter(tabela);
        expect(component.nodesExibidos[0].data.valor_total).toBe(30);
        component.collapseAll();
        expect(component.nodesExibidos[0].children![0].children![0].children![0].expanded).toBeFalse();
        component.globalFilterValue = 'inexistente';
        component.applyGlobalFilter(tabela);
        expect(component.nodesExibidos).toEqual([]);
        expect(component.chartData.datasets).toEqual([]);
        component.clearFilter(tabela);
        expect(component.nodesExibidos).toBe(component.nodes);
        expect(component.chartData.datasets[0].data).toEqual([0, 30]);
    });

    it('usa totais de grupos no gráfico mensal em vez de somar transações', () => {
        component.updateChart([{ data: { tipo_node: 'mes', descricao: 'JAN/2024' }, children: [
            { data: { tipo_node: 'tipo', descricao: 'Receitas', valor_total: 25 }, children: [{ data: { tipo_node: 'transacao', valor: 999 } }] }
        ] }, { data: { tipo_node: 'mes', descricao: 'FEV/2024' }, children: [
            { data: { tipo_node: 'tipo', descricao: 'Receitas', valor_total: 40 }, children: [{ data: { tipo_node: 'transacao', valor: 999 } }] }
        ] }]);
        expect(component.chartData.datasets[0].data).toEqual([25, 40]);
    });

    it('should set mock mode if no pywebview is found', (done) => {
        (window as any).pywebview = undefined;

        
        fixture.detectChanges();
        
        setTimeout(() => {
            expect(component.isMockMode).toBeTrue();
            done();
        }, 1100);
    });

    it('should set success mode if pywebview is found immediately', () => {
        (window as any).pywebview = { 
            api: {
                get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {} }),
                get_transacoes: () => Promise.resolve({ status: 'success', data: { tree: [] } })
            } 
        };
        
        fixture.detectChanges();
        
        expect(component.isMockMode).toBeFalse();
        
        (window as any).pywebview = undefined;
    });

    it('should correctly expand 1 level (mes expanded, tipo collapsed)', () => {
        component.nodes = [
            {
                data: { tipo_node: 'mes' },
                expanded: false,
                children: [
                    {
                        data: { tipo_node: 'tipo' },
                        expanded: false,
                        children: [
                            { data: { tipo_node: 'categoria' }, expanded: false }
                        ]
                    }
                ]
            }
        ];
        
        component.expandLevels(1);
        
        expect(component.nodes[0].expanded).toBeTrue(); // Mes expanded
        expect(component.nodes[0].children![0].expanded).toBeFalse(); // Tipo collapsed
    });
});
