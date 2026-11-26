import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Dashboard } from './dashboard';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { Subject } from 'rxjs';

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

    it('carrega indicadores e apresenta o síndico e os demais membros', async () => {
        const api = { get_dashboard_kpis: jasmine.createSpy().and.resolveTo({ status: 'success', data: {
            gestao: { membros: [{ nome: 'Ana Souza', cargo: 'Síndica' }, { nome: 'Bruno Silva', cargo: 'Conselheiro' },
                { nome: 'Carla Lima', cargo: 'Conselheira' }, { nome: 'Daniel Costa', cargo: 'Subsíndico' },
                { nome: 'Eva Alves', cargo: 'Conselheira' }] }
        } }) };
        component.fetchKpis(api);
        await Promise.resolve();
        expect(component.loadingKpis).toBeFalse();
        expect(component.sindicoName).toBe('Ana Souza');
        expect(component.demaisMembrosList.map(m => m.nome)).toEqual(['Bruno', 'Carla', 'Daniel']);
        expect(component.hiddenMembrosCount).toBe(1);
        expect(component.hiddenMembrosTooltip).toContain('Eva');
    });

    it('consulta transações no intervalo e atualiza árvore e gráfico', async () => {
        component.dateRange = [new Date(2025, 0, 2), new Date(2025, 1, 3)];
        const api = { get_transacoes: jasmine.createSpy().and.resolveTo({ status: 'success', data: {
            prazo_fechamento: 5, tree: [{ data: { tipo_node: 'mes', descricao: 'JAN/2025', competencia: '2025-01' },
                children: [{ data: { tipo_node: 'tipo', descricao: 'Receitas', valor_total: 100 }, children: [] }] }]
        } }) };
        component.fetchTransacoes(api);
        await Promise.resolve();
        expect(api.get_transacoes).toHaveBeenCalledOnceWith('2025-01-02', '2025-02-03');
        expect(component.loadingTreeTable).toBeFalse();
        expect(component.prazoFechamento).toBe(5);
        expect(component.nodes[0].expanded).toBeTrue();
        expect(component.nodes[0].children![0].data.grupo).toBe('Receitas');
        expect(component.getDatePickerLabel()).toBe('02/01/2025 - 03/02/2025');
    });

    it('abre arquivo único e oferece lista quando uma transação tem vários anexos', async () => {
        const abrir = jasmine.createSpy().and.resolveTo({ status: 'success' });
        const anexos = jasmine.createSpy().and.returnValues(
            Promise.resolve({ status: 'success', data: [{ caminho_local: 'anexos/a.pdf' }] }),
            Promise.resolve({ status: 'success', data: [{ caminho_local: 'a.pdf' }, { caminho_local: 'b.pdf' }] })
        );
        (window as any).pywebview = { api: { get_anexos_transacao: anexos, abrir_arquivo_local: abrir } };
        const evento = new MouseEvent('click');
        component.abrirAnexos({ tipo_node: 'transacao', id: 7 }, evento);
        await Promise.resolve();
        expect(abrir).toHaveBeenCalledOnceWith('anexos/a.pdf');
        const painel = { toggle: jasmine.createSpy() };
        component.op = painel as any;
        component.abrirAnexos({ tipo_node: 'transacao', id: 7 }, evento);
        await Promise.resolve();
        expect(component.anexosAtuais.length).toBe(2);
        expect(painel.toggle).toHaveBeenCalledOnceWith(evento);
        delete (window as any).pywebview;
    });

    it('altera período com atalhos e limpa filtro anterior', () => {
        const carregar = spyOn(component, 'fetchTransacoes');
        const reset = jasmine.createSpy();
        (component as any).treeTable = { reset };
        (window as any).pywebview = { api: {} };
        component.globalFilterValue = 'teste';
        const calendario = { hide: jasmine.createSpy() };
        component.setMesAtual(calendario);
        expect(component.dateRange![0].getDate()).toBe(1);
        expect(component.globalFilterValue).toBe('');
        expect(reset).toHaveBeenCalled();
        component.setAnoAtual(calendario);
        expect(component.dateRange![0].getMonth()).toBe(0);
        component.setDesdeOComeco(calendario);
        expect(component.getDatePickerLabel()).toContain('* - ');
        expect(carregar).toHaveBeenCalledTimes(3);
        expect(calendario.hide).toHaveBeenCalledTimes(3);
        delete (window as any).pywebview;
    });

    it('estiliza linhas da árvore por grupo e tipo de nó', () => {
        expect(component.getRowClass(null)).toBe('');
        expect(component.getRowClass({ tipo_node: 'mes' })).toContain('font-bold');
        for (const grupo of ['Despesas', 'Receitas']) {
            const cor = grupo === 'Despesas' ? 'red' : 'green';
            for (const tipo of ['tipo', 'categoria', 'subcategoria', 'transacao']) {
                expect(component.getRowClass({ tipo_node: tipo, grupo })).toContain(cor);
            }
        }
        expect(component.getRowClass({ tipo_node: 'outro', grupo: 'Outro' })).toBe('');
    });

    it('expande todos os níveis da árvore exibida', () => {
        const folha = { data: { tipo_node: 'transacao', valor: 1 }, expanded: false };
        component.nodes = [
            { data: { tipo_node: 'mes' }, expanded: false, children: [
                { data: { tipo_node: 'tipo' }, expanded: false, children: [
                    { data: { tipo_node: 'categoria' }, expanded: false, children: [folha] }
                ] }
            ] },
            { data: { tipo_node: 'mes' }, expanded: false, children: [] }
        ];
        component.expandAll();
        const mes = component.nodes[0];
        expect(mes.expanded).toBeTrue();
        expect(mes.children![0].expanded).toBeFalse();
        expect(component.nodes[1].expanded).toBeFalse();
    });

    it('recolhe o penúltimo nível mantendo o último estado', () => {
        component.nodes = [
            { data: { tipo_node: 'mes' }, expanded: true, children: [
                { data: { tipo_node: 'tipo' }, expanded: true, children: [
                    { data: { tipo_node: 'categoria' }, expanded: true, children: [] }
                ] }
            ] }
        ];
        component.collapseAll();
        expect(component.nodes[0].expanded).toBeTrue();
        expect(component.nodes[0].children![0].expanded).toBeFalse();
    });

    it('expande recursivamente via helper interno', () => {
        const neto = { data: {}, expanded: false, children: [] };
        const filho = { data: {}, expanded: false, children: [neto] };
        const raiz = { data: {}, expanded: false, children: [filho] };
        (component as any).expandRecursive(raiz, true);
        expect([raiz.expanded, filho.expanded, neto.expanded]).toEqual([true, true, true]);
        (component as any).expandRecursive(raiz, false);
        expect([raiz.expanded, filho.expanded, neto.expanded]).toEqual([false, false, false]);
    });

    it('identifica meses dentro do prazo de fechamento', () => {
        component.prazoFechamento = 0;
        expect(component.isMonthOpen({ tipo_node: 'transacao' })).toBeFalse();
        expect(component.isMonthOpen({ tipo_node: 'mes' })).toBeFalse();
        expect(component.isMonthOpen({ tipo_node: 'mes', competencia: 'invalida' })).toBeFalse();
        expect(component.isMonthOpen({ tipo_node: 'mes', descricao: 'JAN/2020' })).toBeFalse();
        expect(component.isMonthOpen({ tipo_node: 'mes', competencia: '2999-12' })).toBeTrue();
        expect(component.isMonthOpen({ tipo_node: 'mes', competencia: '2020-01' })).toBeFalse();
    });

    it('trata erro e rejeição ao buscar KPIs e membros sem síndico', async () => {
        const erro = spyOn(console, 'error');
        component.fetchKpis({ get_dashboard_kpis: () => Promise.resolve({ status: 'error', message: 'falha' }) });
        await Promise.resolve();
        expect(component.loadingKpis).toBeFalse();
        component.fetchKpis({ get_dashboard_kpis: () => Promise.reject(new Error('rede')) });
        await Promise.resolve();
        await Promise.resolve();
        expect(component.loadingKpis).toBeFalse();
        expect(erro).toHaveBeenCalled();

        component.kpis = {};
        component.fetchKpis({ get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {
            gestao: { membros: [{ nome: 'Zelador Um', cargo: '' }, { nome: 'Auxiliar Dois', cargo: 'Conselheiro' }] }
        } }) });
        await Promise.resolve();
        expect(component.sindicoName).toBe('Zelador Um');
        expect(component.demaisMembrosList).toEqual([{ nome: 'Auxiliar', cargo: 'Conselheiro' }]);
        expect(component.hiddenMembrosCount).toBe(0);
        expect(component.hiddenMembrosTooltip).toBe('');
    });

    it('trata erro e rejeição ao buscar transações e expande um nível com vários meses', async () => {
        spyOn(console, 'error');
        component.fetchTransacoes({ get_transacoes: () => Promise.resolve({ status: 'error', message: 'falha' }) });
        await Promise.resolve();
        expect(component.nodes).toEqual([]);
        expect(component.loadingTreeTable).toBeFalse();
        component.fetchTransacoes({ get_transacoes: () => Promise.reject(new Error('rede')) });
        await Promise.resolve();
        await Promise.resolve();
        expect(component.loadingTreeTable).toBeFalse();

        component.dateRange = [new Date(2025, 0, 1), new Date(2025, 2, 1)];
        component.fetchTransacoes({ get_transacoes: () => Promise.resolve({ status: 'success', data: {
            prazo_fechamento: 0,
            tree: [
                { data: { tipo_node: 'mes', descricao: 'JAN/2025', competencia: '2025-01' }, children: [
                    { data: { tipo_node: 'tipo', descricao: 'Receitas' }, children: [] } ] },
                { data: { tipo_node: 'mes', descricao: 'FEV/2025', competencia: '2025-02' }, children: [
                    { data: { tipo_node: 'tipo', descricao: 'Despesas' }, children: [] } ] }
            ]
        } }) });
        await Promise.resolve();
        expect(component.nodes.length).toBe(2);
        expect(component.nodes[0].expanded).toBeTrue();
        expect(component.nodes[0].children![0].expanded).toBeUndefined();
        expect(component.nodes[1].expanded).toBeTrue();
    });

    it('monta o rótulo do seletor de período nos casos extremos', () => {
        component.dateRange = [];
        expect(component.getDatePickerLabel()).toBe('');
        component.dateRange = [null as any, null as any];
        expect(component.getDatePickerLabel()).toBe('');
        component.dateRange = [new Date(2025, 0, 5), null as any];
        expect(component.getDatePickerLabel()).toBe('05/01/2025');
    });

    it('configura callbacks do gráfico para mês único e múltiplos', () => {
        component.initChartOptions();
        const opcoes = component.chartOptions;
        component.isSingleMonth = true;
        expect(opcoes.plugins.tooltip.filter({ parsed: { y: 0 } })).toBeFalse();
        expect(opcoes.plugins.tooltip.filter({ parsed: { y: 10 } })).toBeTrue();
        component.isSingleMonth = false;
        expect(opcoes.plugins.tooltip.filter({ parsed: { y: 0 } })).toBeTrue();
        expect(opcoes.plugins.tooltip.callbacks.label({ dataset: { label: 'Receitas' }, parsed: { y: 1234.5 } })).toContain('Receitas');
        component.chartData = { labels: ['JAN/2024', 'FEV/2024'] };
        const corJan = opcoes.scales.x.ticks.color({ index: 0 });
        const corDemais = opcoes.scales.x.ticks.color({ index: 1 });
        expect(corJan).not.toBe(corDemais);
        expect(opcoes.scales.x.ticks.font({ index: 0 }).weight).toBe('bold');
        expect(opcoes.scales.x.ticks.font({ index: 1 }).weight).toBe(500);
        component.isSingleMonth = true;
        expect(opcoes.scales.x.ticks.color({ index: 0 })).toBe(corDemais);
        expect(opcoes.scales.x.ticks.font({ index: 0 }).weight).toBe(500);
        expect(opcoes.scales.y.ticks.callback(10)).toBe('R$ 10');
    });

    it('gera segmentos tracejados para lacunas e cores por grupo no gráfico', () => {
        component.updateChart([
            { data: { tipo_node: 'mes', descricao: 'JAN/2025' }, children: [
                { data: { tipo_node: 'tipo', descricao: 'Receitas', valor_total: 100 }, children: [
                    { data: { tipo_node: 'categoria', descricao: 'Taxas', valor_total: 100 }, children: [] } ] } ] },
            { data: { tipo_node: 'mes', descricao: 'FEV/2025' }, children: [
                { data: { tipo_node: 'tipo', descricao: 'Despesas', valor_total: 50 }, children: [
                    { data: { tipo_node: 'categoria', descricao: 'Limpeza', valor_total: 50 }, children: [] } ] } ] }
        ]);
        expect(component.isSingleMonth).toBeFalse();
        for (const dataset of component.chartData.datasets) {
            const pulado = { p0: { skip: true }, p1: { skip: false } };
            const cheio = { p0: { skip: false }, p1: { skip: false } };
            expect(dataset.segment.borderDash(pulado)).toEqual([5, 5]);
            expect(dataset.segment.borderWidth(pulado)).toBe(1);
            expect(dataset.segment.borderDash(cheio)).toBeUndefined();
            expect(dataset.segment.borderWidth(cheio)).toBeUndefined();
        }
        expect(component.getCategoryColor(0, 'Receitas')).toBe('#10b981');
        expect(component.getCategoryColor(0, 'Despesas')).toBe('#ef4444');

        component.updateChart([
            { data: { tipo_node: 'mes', descricao: 'MAR/2025' }, children: [
                { data: { tipo_node: 'tipo', descricao: 'Receitas', valor_total: 80 }, children: [
                    { data: { tipo_node: 'categoria', descricao: 'Taxas', valor_total: 80 }, children: [] } ] } ] }
        ]);
        expect(component.isSingleMonth).toBeTrue();
        expect(component.chartData.datasets[0].backgroundColor).toBe('#10b981');
        expect(component.chartData.datasets[0].data).toEqual([80, 0]);
    });

    it('lista anexos em modo simulação, por mês e trata erros', async () => {
        const evento = new MouseEvent('click');
        const painel = { toggle: jasmine.createSpy() };
        component.op = painel as any;

        component.isMockMode = true;
        component.abrirAnexos({ tipo_node: 'transacao', id: 1 }, evento);
        expect(component.anexosAtuais.length).toBe(2);
        expect(painel.toggle).toHaveBeenCalledWith(evento);

        component.isMockMode = false;
        component.abrirAnexos(null, evento);
        component.anexosAtuais = [];
        component.abrirAnexos({ tipo_node: 'transacao', id: 1 }, evento);
        expect(component.anexosAtuais).toEqual([]);

        const erro = spyOn(console, 'error');
        const mes = { tipo_node: 'mes', competencia: '2025-01' };
        (window as any).pywebview = { api: {
            get_prestacoes_contas_mes: jasmine.createSpy().and.resolveTo({ status: 'success', data: [
                { caminho_local: 'a.pdf' }, { caminho_local: 'b.pdf' }
            ] }),
            get_anexos_transacao: jasmine.createSpy().and.callFake(() =>
                Promise.resolve({ status: 'error', message: 'sem anexos' })
            ),
            abrir_arquivo_local: jasmine.createSpy().and.resolveTo({ status: 'error', message: 'falha abrir' })
        } };
        component.abrirAnexos(mes, evento);
        await Promise.resolve();
        expect(component.anexosAtuais.length).toBe(2);
        expect(painel.toggle).toHaveBeenCalledTimes(2);

        component.abrirAnexos({ tipo_node: 'transacao', id: 9 }, evento);
        await Promise.resolve();
        await Promise.resolve();
        expect(erro).toHaveBeenCalled();

        component.abrirArquivo('x.pdf');
        await Promise.resolve();
        await Promise.resolve();
        expect(erro).toHaveBeenCalledWith('Erro ao abrir arquivo:', 'falha abrir');
        delete (window as any).pywebview;
    });

    it('carrega dados quando o evento pywebviewready é disparado', () => {
        delete (window as any).pywebview;
        component.detectEnvironmentAndLoad();
        const buscarKpis = jasmine.createSpy().and.resolveTo({ status: 'success', data: {} });
        const buscarTransacoes = jasmine.createSpy().and.resolveTo({ status: 'success', data: { tree: [] } });
        (window as any).pywebview = { api: { get_dashboard_kpis: buscarKpis, get_transacoes: buscarTransacoes } };
        window.dispatchEvent(new Event('pywebviewready'));
        expect(component.isMockMode).toBeFalse();
        expect(buscarKpis).toHaveBeenCalled();
        expect(buscarTransacoes).toHaveBeenCalled();
        delete (window as any).pywebview;
    });

    it('recarrega transações mockadas ao mudar o período em modo simulação', async () => {
        component.isMockMode = true;
        component.dateRange = [new Date(2025, 0, 1), new Date(2025, 1, 28)];
        component.globalFilterValue = 'antigo';
        const tabela = { reset: jasmine.createSpy() };
        (component as any).treeTable = tabela;
        component.onDateRangeChange();
        expect(component.loadingTreeTable).toBeTrue();
        expect(component.globalFilterValue).toBe('');
        expect(tabela.reset).toHaveBeenCalled();
        await new Promise(resolve => setTimeout(resolve, 900));
        expect(component.nodes.length).toBe(2);
        expect(component.loadingTreeTable).toBeFalse();
        expect(component.chartData.labels.length).toBe(2);
        expect(component.chartData.datasets.length).toBe(2);
    });

    it('assina configUpdate$ quando presente e tolera plugin sem área ou labels', () => {
        const api = {
            get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {} }),
            get_transacoes: () => Promise.resolve({ status: 'success', data: { tree: [] } })
        };
        (window as any).pywebview = { api };
        (component.layoutService as any).configUpdate$ = new Subject<void>();
        component.ngOnInit();
        (component.layoutService as any).configUpdate$.next();
        expect(component.chartOptions).toBeDefined();
        delete (window as any).pywebview;

        component.chartPlugins[0].afterDraw({});
        component.chartPlugins[0].afterDraw({ data: { labels: ['SEM ANO', 'X/2024'] },
            chartArea: { top: 0, bottom: 10 }, scales: { x: { getPixelForValue: () => 0 } }, ctx: {} });
    });

    it('usa a API que chega durante a espera ou cai no modo simulação', async () => {
        jasmine.clock().install();
        try {
            delete (window as any).pywebview;
            component.loadingKpis = true;
            component.detectEnvironmentAndLoad();
            const api = {
                get_dashboard_kpis: jasmine.createSpy().and.resolveTo({ status: 'success', data: {} }),
                get_transacoes: jasmine.createSpy().and.resolveTo({ status: 'success', data: { tree: [] } })
            };
            (window as any).pywebview = { api };
            jasmine.clock().tick(1000);
            await Promise.resolve();
            await Promise.resolve();
            expect(api.get_dashboard_kpis).toHaveBeenCalled();
            expect(api.get_transacoes).toHaveBeenCalled();

            component.isMockMode = false;
            component.loadingKpis = true;
            component.loadingTreeTable = true;
            delete (window as any).pywebview;
            component.detectEnvironmentAndLoad();
            (window as any).pywebview = {};
            jasmine.clock().tick(1000);
            expect(component.isMockMode).toBeTrue();
        } finally {
            jasmine.clock().uninstall();
            delete (window as any).pywebview;
        }
    });

    it('expande níveis aninhados e usa nós filtrados no expandAll', () => {
        const folha = { data: { tipo_node: 'transacao', valor: 1 }, expanded: false };
        component.nodes = [
            { data: { tipo_node: 'mes' }, expanded: true, children: [
                { data: { tipo_node: 'tipo' }, expanded: false, children: [folha] }
            ] },
            { data: { tipo_node: 'mes' }, expanded: false, children: [] }
        ];
        component.expandAll();
        expect(component.nodes[0].children![0].expanded).toBeTrue();
        expect(component.nodes[1].expanded).toBeFalse();

        (component as any).nodesFiltrados = [...component.nodes];
        component.expandAll();
        expect((component as any).nodesFiltrados[0].children![0].expanded).toBeTrue();
        (component as any).nodesFiltrados = null;
    });

    it('limpa filtro vazio e cobre fallbacks do filtro global', () => {
        const tabela = { reset: jasmine.createSpy(), filterGlobal: jasmine.createSpy() };
        component.nodes = component.processNodes([{ data: { tipo_node: 'mes', descricao: 'JAN/2024', valor_total: 0 }, children: [
            { data: { tipo_node: 'tipo', descricao: 'Despesas', valor_total: 0 }, children: [
                { data: { tipo_node: 'categoria', descricao: 'Geral', valor_total: 0 }, children: [
                    { data: { tipo_node: 'subcategoria', descricao: 'S' }, children: [
                        { data: { tipo_node: 'transacao', descricao: 'Alvo', apartamento: null, valor: 0 } },
                        { data: { tipo_node: 'transacao', descricao: 'Outro', apartamento: '101', valor: null } }
                    ] }
                ] }
            ] },
            { data: { tipo_node: 'sem_filhos', descricao: 'Vazio' } }
        ] }]);
        component.globalFilterValue = '';
        component.applyGlobalFilter(tabela);
        expect((component as any).nodesFiltrados).toBeNull();

        component.globalFilterValue = '101';
        component.applyGlobalFilter(tabela);
        const sub = component.nodesExibidos[0].children![0].children![0].children![0];
        expect(sub.data.porcentagem).toBe(0);
        expect(component.nodesExibidos[0].children!.some(c => c.data.descricao === 'Vazio')).toBeFalse();
    });

    it('monta gráfico mensal com nós e valores ausentes', () => {
        component.updateChart(null as any);
        expect(component.isSingleMonth).toBeTrue();
        expect(component.chartData.datasets).toEqual([]);

        component.updateChart([{ data: { tipo_node: 'mes', descricao: 'JAN/2024' } }] as any);
        expect(component.chartData.datasets).toEqual([]);

        component.updateChart([
            { data: { tipo_node: 'mes', descricao: 'JAN/2024' }, children: [
                { data: { tipo_node: 'tipo', descricao: 'Receitas' }, children: [
                    { data: { tipo_node: 'categoria', descricao: 'R' }, children: [] }
                ] },
                { data: { tipo_node: 'tipo', descricao: 'Despesas', valor_total: 30 }, children: [
                    { data: { tipo_node: 'categoria', descricao: 'D', valor_total: 30 }, children: [] }
                ] },
                { data: { tipo_node: 'tipo', descricao: 'Outros' } }
            ] }
        ] as any);
        expect(component.isSingleMonth).toBeTrue();
        expect(component.chartData.datasets.length).toBe(2);
        expect(component.chartData.datasets[0].data).toEqual([0, 0]);
        expect(component.chartData.datasets[1].data).toEqual([0, 30]);

        component.updateChart([
            { data: { tipo_node: 'mes', descricao: 'MAR/2024' } },
            { data: { tipo_node: 'mes', descricao: 'ABR/2024' }, children: [
                { data: { tipo_node: 'tipo', descricao: 'Receitas' } }
            ] }
        ] as any);
        expect(component.isSingleMonth).toBeFalse();
        expect(component.chartData.datasets[0].data[0]).toBeNaN();
        expect(component.chartData.datasets[1].data[0]).toBeNaN();
    });

    it('cobra callbacks do tooltip e ticks sem dados de gráfico', () => {
        component.initChartOptions();
        const opcoes = component.chartOptions;
        expect(opcoes.plugins.tooltip.callbacks.label({ dataset: { label: '' }, parsed: { y: 10 } })).toContain('10');
        expect(opcoes.plugins.tooltip.callbacks.label({ dataset: { label: 'Receitas' }, parsed: { y: null } })).toBe('Receitas: ');
        component.isSingleMonth = false;
        component.chartData = null;
        expect(opcoes.scales.x.ticks.color({ index: 0 })).toBeTruthy();
        expect(opcoes.scales.x.ticks.font({ index: 0 }).weight).toBe(500);
    });

    it('trata anexos sem dados, rejeições e membro sem cargo', async () => {
        const erro = spyOn(console, 'error');
        const evento = new MouseEvent('click');
        (window as any).pywebview = { api: {
            get_anexos_transacao: jasmine.createSpy().and.callFake(() => Promise.resolve({ status: 'success' })),
            get_prestacoes_contas_mes: jasmine.createSpy().and.callFake(() => Promise.reject(new Error('rede'))),
            abrir_arquivo_local: () => Promise.resolve({ status: 'success' })
        } };
        component.isMockMode = false;
        component.abrirAnexos({ tipo_node: 'transacao', id: 1 }, evento);
        await Promise.resolve();
        expect(component.anexosAtuais).toEqual([]);
        component.abrirAnexos({ tipo_node: 'mes', competencia: '2025-01' }, evento);
        await Promise.resolve();
        await Promise.resolve();
        expect(erro).toHaveBeenCalled();

        const rejeitar = jasmine.createSpy().and.callFake(() => Promise.reject(new Error('rede')));
        (window as any).pywebview.api.get_anexos_transacao = rejeitar;
        component.abrirAnexos({ tipo_node: 'transacao', id: 2 }, evento);
        await Promise.resolve();
        await Promise.resolve();
        expect(erro).toHaveBeenCalled();

        component.fetchKpis({ get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {
            gestao: { membros: [{ nome: 'Síndico Um', cargo: 'Síndico' }, { nome: 'Sem Cargo' }] }
        } }) });
        await Promise.resolve();
        expect(component.demaisMembrosList[0].cargo).toBe('Membro');
        delete (window as any).pywebview;
    });
});
