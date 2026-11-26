import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Table } from 'primeng/table';
import { DialogService } from 'primeng/dynamicdialog';
import { Subject } from 'rxjs';
import { RevisaoComponent } from './revisao';

describe('Estado da tabela de revisão', () => {
    let fixture: ComponentFixture<RevisaoComponent>;
    let component: RevisaoComponent;
    let pendentes: any[];
    let revisados: any[];
    let estadoAnterior: Map<string, string | null>;
    const chaves = ['meses', 'categorias', 'subcategorias', 'lancamentos', 'documentos']
        .map(tipo => `winker-revisao-${tipo}`);
    const chaveMeses = 'winker-revisao-meses';
    const outraChave = 'winker-teste-outra-tabela';

    function meses(prefixo: string, quantidade: number): any[] {
        return Array.from({ length: quantidade }, (_, i) => ({
            id: i + 1, exibicao: `${prefixo} ${String(i).padStart(2, '0')}`,
            competencia: '2026-01', receita_total: 100, despesa_total: 50, motivo_inconsistencia: '[]'
        }));
    }

    async function atualizarTela() {
        for (let i = 0; i < 3; i++) {
            fixture.detectChanges(false);
            await fixture.whenStable();
        }
        fixture.detectChanges(false);
    }

    function tabela(): Table {
        return fixture.debugElement.query(By.directive(Table)).componentInstance as Table;
    }

    beforeEach(async () => {
        estadoAnterior = new Map([...chaves, outraChave].map(chave => [chave, sessionStorage.getItem(chave)]));
        chaves.forEach(chave => sessionStorage.removeItem(chave));
        sessionStorage.setItem(outraChave, 'preservar');
        pendentes = meses('Pendente', 25);
        revisados = meses('Revisado', 1);
        (window as any).pywebview = { api: {
            get_pendencias_revisao_count: (exibirRevisados: boolean) => Promise.resolve({
                status: 'success', data: { details: { meses: (exibirRevisados ? revisados : pendentes).length, categorias: 1 } }
            }),
            get_registros_nao_revisados: (tipo: string, exibirRevisados: boolean) => Promise.resolve({
                status: 'success', data: tipo === 'meses' ? (exibirRevisados ? revisados : pendentes) : [{
                    id: 1, nome: 'Categoria de teste', valor: 100, motivo_inconsistencia: '[]'
                }]
            })
        }};
        await TestBed.configureTestingModule({ imports: [RevisaoComponent] }).compileComponents();
        fixture = TestBed.createComponent(RevisaoComponent);
        component = fixture.componentInstance;
    });

    afterEach(() => {
        delete (window as any).pywebview;
        estadoAnterior.forEach((valor, chave) => {
            if (valor === null) sessionStorage.removeItem(chave);
            else sessionStorage.setItem(chave, valor);
        });
    });

    it('ao alternar revisados mostra a primeira página do novo conjunto', async () => {
        sessionStorage.setItem(chaveMeses, JSON.stringify({
            first: 20, rows: 10, multiSortMeta: [{ field: 'exibicao', order: 1 }]
        }));
        for (const chave of chaves.filter(chave => chave !== chaveMeses)) {
            sessionStorage.setItem(chave, JSON.stringify({ first: 20, rows: 10 }));
        }

        await atualizarTela();
        expect(tabela().first).toBe(20);
        expect(fixture.nativeElement.textContent).toContain('Pendente 20');

        const toggle = fixture.nativeElement.querySelector('p-toggleswitch input') as HTMLInputElement;
        expect(toggle).toBeTruthy();
        toggle.click();
        await atualizarTela();

        expect(component.activeTab).toBe('3');
        expect(tabela().first).toBe(0);
        expect(tabela().multiSortMeta || []).toEqual([]);
        expect(fixture.nativeElement.textContent).toContain('Revisado 00');
        for (const chave of chaves.filter(chave => chave !== chaveMeses)) {
            expect(sessionStorage.getItem(chave)).toBeNull();
        }
        expect(sessionStorage.getItem(outraChave)).toBe('preservar');
    });

    it('preserva página e ordenação ao salvar na mesma visão', async () => {
        sessionStorage.setItem(chaveMeses, JSON.stringify({
            first: 20, rows: 10, multiSortMeta: [{ field: 'exibicao', order: 1 }]
        }));
        await atualizarTela();
        expect(tabela().first).toBe(20);
        const fechamento = new Subject<any>();
        spyOn(fixture.debugElement.injector.get(DialogService), 'open')
            .and.returnValue({ onClose: fechamento.asObservable() } as any);

        component.editRow(pendentes[20], 'meses');
        fechamento.next({ status: 'success', message: 'Salvo' });
        await atualizarTela();

        expect(component.activeTab).toBe('3');
        expect(tabela().first).toBe(20);
        expect(tabela().multiSortMeta).toEqual([{ field: 'exibicao', order: 1 }]);
        expect(fixture.nativeElement.textContent).toContain('Pendente 20');
    });

    it('também volta à primeira página ao ocultar registros revisados', async () => {
        pendentes = meses('Pendente', 1);
        revisados = meses('Revisado', 25);
        component.exibirRevisados = true;
        sessionStorage.setItem(chaveMeses, JSON.stringify({ first: 20, rows: 10 }));
        await atualizarTela();
        expect(tabela().first).toBe(20);
        expect(fixture.nativeElement.textContent).toContain('Revisado 20');

        (fixture.nativeElement.querySelector('p-toggleswitch input') as HTMLInputElement).click();
        await atualizarTela();

        expect(component.exibirRevisados).toBeFalse();
        expect(tabela().first).toBe(0);
        expect(fixture.nativeElement.textContent).toContain('Pendente 00');
    });

    it('seleciona a primeira aba disponível ao alternar a visão', async () => {
        component.activeTab = '2';
        await atualizarTela();
        expect(component.activeTab).toBe('2');
        expect(fixture.nativeElement.textContent).toContain('Categoria de teste');

        (fixture.nativeElement.querySelector('p-toggleswitch input') as HTMLInputElement).click();
        await atualizarTela();

        expect(component.activeTab).toBe('3');
        expect(fixture.nativeElement.textContent).toContain('Revisado 00');
    });

    it('seleciona a primeira categoria com pendências e carrega cada aba uma vez', async () => {
        component.activeTab = '-1';
        component.pendenciasCounts = { meses: 0, categorias: 0, subcategorias: 2, lancamentos: 1, documentos: 1 };
        const carregar = spyOn(component, 'loadTableData');
        component.setDefaultTab();
        expect(component.activeTab).toBe('1');
        expect(carregar).toHaveBeenCalledOnceWith('subcategorias');
        component.subcategorias = [{ id: 1 }];
        component.onTabChange('1');
        expect(carregar).toHaveBeenCalledTimes(1);
        component.onTabChange('4');
        expect(carregar).toHaveBeenCalledWith('documentos');
        component.pendenciasCounts = { meses: 0, categorias: 0, subcategorias: 0, lancamentos: 0, documentos: 0 };
        component.setDefaultTab();
        expect(component.activeTab).toBe('-1');
    });

    it('interpreta motivos em JSON e texto legado e conta as inconsistências', async () => {
        (window as any).pywebview.api.get_registros_nao_revisados = () => Promise.resolve({ status: 'success', data: [
            { id: 1, motivo_inconsistencia: '["Primeiro", "Segundo"]' },
            { id: 2, motivo_inconsistencia: 'Primeiro | Segundo | ' },
            { id: 3, motivo_inconsistencia: '' }
        ] });
        component.loadTableData('lancamentos');
        await Promise.resolve();
        expect(component.lancamentos.map(item => item.inconsistencias_count)).toEqual([2, 2, 0]);
        expect(component.getInconsistenciasList('Um | Dois')).toEqual(['Um', 'Dois']);
        expect(component.getAvatarLabelMes('2025-04')).toBe('04');
        expect(component.loadingLancamentos).toBeFalse();
    });

    it('usa contagens zeradas quando a resposta não traz detalhes e cobre catch', async () => {
        (window as any).pywebview.api.get_pendencias_revisao_count = () => Promise.resolve({ status: 'success', data: {} });
        component.loadCounts();
        await Promise.resolve();
        expect(component.pendenciasCounts).toEqual({ lancamentos: 0, subcategorias: 0, categorias: 0, meses: 0, documentos: 0 });
        (window as any).pywebview.api.get_pendencias_revisao_count = () => Promise.reject(new Error('rede'));
        component.loadCounts();
        await Promise.resolve();
        await Promise.resolve();
        expect(component.loadingCounts).toBeFalse();
    });

    it('seleciona abas por tipo de pendência restante', () => {
        const casos: [any, string][] = [
            [{ meses: 0, categorias: 0, subcategorias: 0, lancamentos: 3, documentos: 0 }, '0'],
            [{ meses: 0, categorias: 0, subcategorias: 4, lancamentos: 0, documentos: 0 }, '1'],
            [{ meses: 0, categorias: 2, subcategorias: 0, lancamentos: 0, documentos: 0 }, '2'],
            [{ meses: 1, categorias: 2, subcategorias: 0, lancamentos: 0, documentos: 0 }, '3'],
            [{ meses: 0, categorias: 0, subcategorias: 0, lancamentos: 0, documentos: 5 }, '4']
        ];
        for (const [counts, aba] of casos) {
            component.pendenciasCounts = counts;
            component.activeTab = '-1';
            component.setDefaultTab();
            expect(component.activeTab).toBe(aba);
        }
    });

    it('carrega dados mockados de cada tabela sem backend', () => {
        delete (window as any).pywebview;
        const anterior = (window as any).__mockHasInconsistencies;
        (window as any).__mockHasInconsistencies = true;
        try {
            component.loadTableData('lancamentos');
            expect(component.lancamentos.length).toBe(2);
            component.loadTableData('meses');
            expect(component.meses.length).toBe(1);
            component.loadTableData('documentos');
            expect(component.documentos.length).toBe(1);
            component.loadTableData('categorias');
            expect(component.categorias.length).toBe(1);
            component.loadTableData('subcategorias');
            expect(component.subcategorias.length).toBe(1);
            (window as any).__mockHasInconsistencies = false;
            component.loadTableData('lancamentos');
            expect(component.lancamentos).toEqual([]);
        } finally {
            if (anterior === undefined) delete (window as any).__mockHasInconsistencies;
            else (window as any).__mockHasInconsistencies = anterior;
        }
    });

    it('usa contagens mockadas sem backend e trata erro na listagem', async () => {
        delete (window as any).pywebview;
        const anterior = (window as any).__mockHasInconsistencies;
        (window as any).__mockHasInconsistencies = true;
        try {
            component.loadCounts();
            expect(component.pendenciasCounts.lancamentos).toBe(5);
            expect(component.loadingCounts).toBeFalse();
        } finally {
            if (anterior === undefined) delete (window as any).__mockHasInconsistencies;
            else (window as any).__mockHasInconsistencies = anterior;
        }
        (window as any).pywebview = { api: {
            get_registros_nao_revisados: () => Promise.resolve({ status: 'error', message: 'falha' })
        } };
        component.loadTableData('meses');
        await Promise.resolve();
        expect(component.loadingMeses).toBeFalse();
        (window as any).pywebview.api.get_registros_nao_revisados = () => Promise.reject(new Error('rede'));
        component.loadTableData('meses');
        await Promise.resolve();
        await Promise.resolve();
        expect(component.loadingMeses).toBeFalse();
    });

    it('formata avatar de mês nos casos extremos', () => {
        expect(component.getAvatarColor('')).toBe('#cbd5e1');
        expect(component.getAvatarColor('2025')).toBe('#cbd5e1');
        expect(component.getAvatarColor('2025-01')).toBe('#f87171');
        expect(component.getAvatarLabelMes('')).toBe('');
        expect(component.getAvatarLabelMes('2025')).toBe('');
        expect(component.getAvatarLabelMes('2025-11')).toBe('11');
    });

    it('recarrega dados ao alternar a visão de revisados', () => {
        const carregar = spyOn(component, 'loadCounts');
        component.onToggleChange();
        expect(sessionStorage.getItem('winker-revisao-meses')).toBeNull();
        expect(component.activeTab).toBe('-1');
        expect(component.meses).toEqual([]);
        expect(carregar).toHaveBeenCalled();
    });
});
