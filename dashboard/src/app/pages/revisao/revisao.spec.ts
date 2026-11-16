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
});
