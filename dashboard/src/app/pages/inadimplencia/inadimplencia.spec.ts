import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InadimplenciaComponent } from './inadimplencia';

describe('InadimplenciaComponent', () => {
    let fixture: ComponentFixture<InadimplenciaComponent>;
    let component: InadimplenciaComponent;

    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [InadimplenciaComponent] }).compileComponents();
        fixture = TestBed.createComponent(InadimplenciaComponent);
        component = fixture.componentInstance;
    });

    afterEach(() => {
        delete window.pywebview;
    });

    it('exibe a conciliação pendente sem informar ausência de inadimplência', async () => {
        const consulta = jasmine.createSpy('get_inadimplencia').and.returnValues(
            Promise.resolve({ status: 'success', data: [] }),
            Promise.resolve({ status: 'error', message: 'Conciliação pendente para a unidade 101' })
        );
        window.pywebview = { api: { get_inadimplencia: consulta } };

        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain('Sem Inadimplência');

        await component.carregarDados();
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain('Conciliação pendente para a unidade 101');
        expect(fixture.nativeElement.textContent).not.toContain('Sem Inadimplência');
        expect(component.inadimplencias).toEqual([]);
    });

    it('consulta a data selecionada e apresenta taxas e totais por unidade', async () => {
        component.dataCorte = new Date(2025, 0, 9);
        const consulta = jasmine.createSpy().and.resolveTo({ status: 'success', data: [
            { unidade: '101', taxas: [
                { competencia: '2025-01', vencimento: '2025-01-10', valor: 100, multa: 2, juros_total: 3 },
                { competencia: '2025-02', vencimento: '15/02/2025', valor: 200, multa: 0, juros_total: 1 }
            ] }
        ] });
        window.pywebview = { api: { get_inadimplencia: consulta } };
        await component.carregarDados();
        expect(consulta).toHaveBeenCalledOnceWith('2025-01-09');
        expect(component.loading).toBeFalse();
        expect(component.activeTab).toBe('101');
        const unidade = component.inadimplencias[0];
        expect(unidade.taxas.map((t: any) => [t.vencimento, t.vencimento_sort, t.total])).toEqual([
            ['10/01/2025', '2025-01-10', 105], ['15/02/2025', '2025-02-15', 201]
        ]);
        expect(component.somarColuna(unidade, 'total')).toBe(306);
        expect(component.somarColuna(unidade, 'valor')).toBe(300);
        expect(component.somarColuna(null, 'valor')).toBe(0);
        expect(component.getAvatarLabelMes('2025-01')).toBe('01');
        expect(component.getAvatarLabelMes('')).toBe('--');
        expect(component.getAvatarColor('2025-01')).toBe(component.getAvatarColor('2025-01'));
    });

    it('limpa resultados e informa erro quando a comunicação falha', async () => {
        component.inadimplencias = [{ unidade: '101' }];
        window.pywebview = { api: { get_inadimplencia: jasmine.createSpy().and.rejectWith(new Error('falha')) } };
        spyOn(console, 'error');
        await component.carregarDados();
        expect(component.inadimplencias).toEqual([]);
        expect(component.erroCarregamento).toBe('Erro ao se comunicar com o backend');
        expect(component.loading).toBeFalse();
    });

    it('retorna para a data atual, atualiza o calendário e recarrega', async () => {
        const carregar = spyOn(component, 'carregarDados').and.resolveTo();
        fixture.detectChanges();
        carregar.calls.reset();
        const calendario = { writeValue: jasmine.createSpy(), updateInputfield: jasmine.createSpy(), hide: jasmine.createSpy() };
        const evento = new MouseEvent('click', { cancelable: true });
        component.dataCorte = new Date(2020, 0, 1);
        component.setDiaAtual(calendario, evento);
        await new Promise(resolve => setTimeout(resolve, 30));
        expect(evento.defaultPrevented).toBeTrue();
        expect(component.dataCorte.toDateString()).toBe(new Date().toDateString());
        expect(calendario.writeValue).toHaveBeenCalledOnceWith(component.dataCorte);
        expect(calendario.updateInputfield).toHaveBeenCalled();
        expect(calendario.hide).toHaveBeenCalled();
        expect(carregar).toHaveBeenCalledTimes(1);
    });

    it('encerra carregamento com mensagem de erro retornada pelo backend', async () => {
        window.pywebview = { api: { get_inadimplencia: jasmine.createSpy().and.resolveTo({ status: 'error', message: 'Erro de teste' }) } };
        await component.carregarDados();
        expect(component.loading).toBeFalse();
        expect(component.erroCarregamento).toBe('Erro de teste');
        expect(component.inadimplencias).toEqual([]);
    });

    it('usa dados mockados quando o backend não está disponível', async () => {
        delete window.pywebview;
        await component.carregarDados();
        expect(component.loading).toBeFalse();
        expect(component.inadimplencias.length).toBe(2);
        expect(component.activeTab).toBe('101');
        const unidade = component.inadimplencias[0];
        expect(unidade.taxas[0].vencimento).toBe('15/06/2026');
        expect(unidade.taxas[0].vencimento_sort).toBe('2026-06-15');
        expect(unidade.taxas[0].total).toBe(367.5);
        expect(component.somarColuna(unidade, 'total')).toBe(726);
        expect(component.somarColuna(unidade, 'valor')).toBe(700);
        expect(component.somarColuna({ unidade: '999' }, 'valor')).toBe(0);
    });

    it('cobra cor de avatar padrão para competência vazia', () => {
        expect(component.getAvatarColor('')).toBe('#f43f5e');
        expect(component.getAvatarColor('2025-01')).not.toBe('#f43f5e');
        expect(component.getAvatarLabelMes('123')).toBe('--');
        expect(component.getAvatarLabelMes('2025-11')).toBe('11');
    });
});
