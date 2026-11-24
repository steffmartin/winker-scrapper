import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RelatoriosComponent } from './relatorios';
import { ExtratoRecebimentosComponent } from './extrato-recebimentos';
import { By } from '@angular/platform-browser';
import { MultiSelect } from 'primeng/multiselect';
import { MessageService } from 'primeng/api';
import { RelatorioInadimplenciaComponent } from './relatorio-inadimplencia';
import { ExtratoContaComponent } from './extrato-conta';

describe('RelatoriosComponent', () => {
    let fixture: ComponentFixture<RelatoriosComponent>;
    let component: RelatoriosComponent;
    const relatorio = (filtros: any) => Promise.resolve(filtros.limites
        ? { status: 'success', data: { limites: { inicio: '2023-01-01', fim: '2023-12-31' } } }
        : { status: 'success', data: { data_corte: '2023-12-31', total: 0, limites: { inicio: '2023-01-01', fim: '2023-12-31' }, apartamentos: [{ apartamento: '101', subtotal: 0, competencias: [] }] } });

    beforeEach(async () => {
        window.pywebview = { api: { get_apartamentos: () => Promise.resolve({ status: 'success', data: ['101', '102'] }), get_relatorio_recebimentos: relatorio } };
        await TestBed.configureTestingModule({ imports: [RelatoriosComponent] }).compileComponents();
        fixture = TestBed.createComponent(RelatoriosComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    afterEach(() => { delete window.pywebview; });

    it('consulta apartamentos somente ao selecionar o extrato de recebimentos', async () => {
        const consulta = jasmine.createSpy('get_apartamentos').and.resolveTo({ status: 'success', data: ['101'] });
        window.pywebview = { api: { get_apartamentos: consulta, get_relatorio_recebimentos: relatorio } };
        await fixture.whenStable();
        expect(consulta).not.toHaveBeenCalled();

        component.relatorioSelecionado = 'extrato-recebimentos';
        await component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        await fixture.whenStable();
        expect(consulta).toHaveBeenCalledTimes(1);
    });

    it('carrega e gera o relatório de inadimplência ao selecioná-lo', async () => {
        const apartamentos = jasmine.createSpy('get_apartamentos').and.resolveTo({ status: 'success', data: ['101'] });
        const gerar = jasmine.createSpy('get_relatorio_inadimplencia').and.resolveTo({ status: 'success', data: {
            data_corte: '2024-03-01', total: 20, apartamentos: [{ apartamento: '101', subtotal: 20, competencias: [
                { competencia: '2024-01', subtotal: 20, taxas: [{ id: 1, vencimento: '2024-01-10', descricao: 'Taxa', valor: 20 }] }
            ] }]
        } });
        window.pywebview = { api: { get_apartamentos: apartamentos, get_relatorio_inadimplencia: gerar } };
        expect(apartamentos).not.toHaveBeenCalled();
        component.relatorioSelecionado = 'inadimplencia';
        await component.alterarRelatorio();
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        const formulario = fixture.debugElement.query(By.directive(RelatorioInadimplenciaComponent)).componentInstance as RelatorioInadimplenciaComponent;
        formulario.dataCorte = new Date(2024, 2, 1);
        formulario.selecionados = ['101'];
        formulario.gerarRelatorio();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        expect(gerar).toHaveBeenCalledWith({ data_corte: '2024-03-01', apartamentos: ['101'] });
        const resultado: HTMLElement = fixture.nativeElement.querySelector('.relatorio-impressao');
        expect(resultado.textContent).toContain('Apartamento 101');
        expect(resultado.textContent).toContain('Total geral');
        expect(resultado.querySelector('[aria-label="Salvar relatório"]')).not.toBeNull();
        expect(resultado.querySelector('[aria-label="Imprimir relatório"]')).not.toBeNull();
    });

    it('carrega o extrato de conta sob demanda e apresenta os saldos do backend', async () => {
        const carregar = jasmine.createSpy('get_contas_relatorio').and.resolveTo({ status: 'success', data: ['Conta A'] });
        const gerar = jasmine.createSpy('get_relatorio_conta').and.resolveTo({ status: 'success', data: {
            periodo: ['2024-01-01', '2024-01-31'], saldo_global: 120, contas: [{ conta: 'Conta A', saldo_anterior: 100,
                subtotal: 20, saldo_final: 120, provisorio: false, meses: [] }]
        } });
        window.pywebview = { api: { get_contas_relatorio: carregar, get_relatorio_conta: gerar } };
        expect(carregar).not.toHaveBeenCalled();
        component.relatorioSelecionado = 'extrato-conta';
        await component.alterarRelatorio();
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        const formulario = fixture.debugElement.query(By.directive(ExtratoContaComponent)).componentInstance as ExtratoContaComponent;
        formulario.periodo = [new Date(2024, 0, 1), new Date(2024, 0, 31)];
        formulario.selecionadas = ['Conta A'];
        formulario.gerarRelatorio();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        expect(gerar).toHaveBeenCalledWith({ periodo: ['2024-01-01', '2024-01-31'], contas: ['Conta A'] });
        const resultado: HTMLElement = fixture.nativeElement.querySelector('.relatorio-impressao');
        expect(resultado.textContent).toContain('Conta A');
        expect(resultado.textContent).toContain('Saldo final');
        expect(resultado.textContent).toContain('Total geral');
        expect(resultado.querySelector('[aria-label="Salvar relatório"]')).not.toBeNull();
        expect(resultado.querySelector('[aria-label="Imprimir relatório"]')).not.toBeNull();
    });

    it('apresenta uma tabela por mês e destaca o último lançamento de cada dia', () => {
        const resultado = TestBed.createComponent(ExtratoContaComponent);
        resultado.componentInstance.modo = 'resultado';
        const transacao = (id: number, data: string) => ({ id, data, descricao: 'Lançamento', tipo: 'Receita', valor: 10, saldo: 10 });
        resultado.componentInstance.dados = { periodo: ['2024-01-01', '2024-01-31'], saldo_global: 30, contas: [{ conta: 'A', saldo_anterior: 0, subtotal: 30, saldo_final: 30, provisorio: false, meses: [{ mes: '2024-01', subtotal: 30, dias: [
            { data: '2024-01-01', subtotal: 20, saldo_final: 20, transacoes: [transacao(1, '2024-01-01'), transacao(2, '2024-01-01')] },
            { data: '2024-01-02', subtotal: 10, saldo_final: 30, transacoes: [transacao(3, '2024-01-02')] }
        ] }] }] };
        resultado.detectChanges();
        expect(resultado.nativeElement.querySelectorAll('table').length).toBe(1);
        const linhas = resultado.nativeElement.querySelectorAll('tbody tr');
        expect(linhas[0].children[0].classList.contains('font-bold')).toBeFalse();
        expect(linhas[1].children[0].classList.contains('font-bold')).toBeTrue();
        expect(linhas[1].children[5].classList.contains('font-bold')).toBeTrue();
        expect(linhas[1].children[2].classList.contains('font-bold')).toBeFalse();
        expect(linhas[2].children[0].classList.contains('font-bold')).toBeTrue();
        expect(resultado.nativeElement.textContent).not.toContain('Subtotal do dia');
        expect(resultado.nativeElement.textContent).not.toContain('Saldo do dia');
    });

    it('substitui resultado anterior pelo skeleton e exibe erros do backend', async () => {
        component.extratoGerado = { data_corte: '2023-01-01', total: 0, apartamentos: [] };
        let resolver!: (valor: any) => void;
        window.pywebview = { api: { get_relatorio_recebimentos: () => new Promise(resolve => { resolver = resolve; }) } };
        const chamada = component.gerarExtrato({ tipo: 'competencia', periodo: null, apartamentos: [] });
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.relatorio-impressao')).toBeNull();
        expect(fixture.nativeElement.querySelector('[aria-busy="true"]')).not.toBeNull();
        resolver({ status: 'error', message: 'Selecione o início e o fim do período.' });
        await chamada;
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('Selecione o início');
    });

    it('separa valores por sinal e apresenta subtotais por competência e apartamento', () => {
        const resultado = TestBed.createComponent(ExtratoRecebimentosComponent);
        resultado.componentInstance.modo = 'resultado';
        const lancamento = (id: number, valor: number) => ({ id, valor, data: '2023-01-10', descricao: 'Teste', tipo: 'Cobrança', desconto_vista: 0, renegociado: false });
        resultado.componentInstance.dados = { data_corte: '2023-12-31', total: 80, apartamentos: [{ apartamento: '101', subtotal: 80, competencias: [
            { competencia: '2023-01', subtotal: 70, lancamentos: [lancamento(1, 100), lancamento(2, -30), { ...lancamento(4, 200), renegociado: true }] },
            { competencia: '2023-02', subtotal: 10, lancamentos: [lancamento(3, 10)] }
        ] }] };
        resultado.detectChanges();
        const tabelas = resultado.nativeElement.querySelectorAll('table');
        expect(tabelas.length).toBe(2);
        const linhas = tabelas[0].querySelectorAll('tbody tr');
        expect(linhas[0].children[3].textContent).toContain('100.00');
        expect(linhas[0].children[4].textContent.trim()).toBe('');
        expect(linhas[1].children[3].textContent.trim()).toBe('');
        expect(linhas[1].children[4].textContent).toContain('30.00');
        expect(tabelas[0].querySelector('tfoot').textContent).toContain('70.00');
        expect(resultado.nativeElement.textContent).toContain('80.00');
    });

    it('gera uma cópia dos parâmetros e oferece impressão apenas no resultado', async () => {
        await fixture.whenStable();
        expect(fixture.nativeElement.textContent).toContain('Nenhum relatório selecionado');
        component.relatorioSelecionado = 'extrato-recebimentos';
        await component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));

        const formulario = fixture.debugElement.query(By.directive(ExtratoRecebimentosComponent)).componentInstance as ExtratoRecebimentosComponent;
        expect(formulario.apartamentos).toEqual(['101', '102']);
        const seletor = fixture.nativeElement.querySelector('p-multiselect');
        expect((seletor.textContent.match(/Todos os apartamentos/g) || []).length).toBe(1);
        expect(formulario.tipo).toBe('completo');
        expect((fixture.nativeElement.querySelector('#extrato-periodo') as HTMLInputElement).disabled).toBeTrue();
        formulario.apartamentosSelecionados = ['101'];
        fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();

        const resultado: HTMLElement = fixture.nativeElement.querySelector('.relatorio-impressao');
        expect(resultado.textContent).toContain('101');
        expect(resultado.textContent).toContain('Parâmetros do relatório');
        expect(resultado.textContent).toContain('01/2023');
        expect(resultado.textContent).toContain('12/2023');
        expect(resultado.textContent).toContain('31/12/2023');
        expect(resultado.textContent).not.toContain('data do sistema');
        expect((resultado.querySelector('[aria-label="Salvar relatório"]') as HTMLButtonElement).disabled).toBeFalse();
        const imprimir = spyOn(window, 'print');
        (resultado.querySelector('[aria-label="Imprimir relatório"]') as HTMLButtonElement).click();
        expect(imprimir).toHaveBeenCalled();

        formulario.apartamentosSelecionados!.push('102');
        fixture.detectChanges();
        expect(resultado.textContent).toContain('101');
        expect(resultado.textContent).not.toContain('102');
        component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.relatorio-impressao')).toBeNull();
    });

    it('salva o relatório e trata cancelamento e erro', async () => {
        const salvar = jasmine.createSpy('salvar_relatorio_pdf').and.returnValues(
            Promise.resolve({ status: 'success' }), Promise.resolve({ status: 'cancelled' }),
            Promise.resolve({ status: 'error', message: 'Falha ao salvar' })
        );
        window.pywebview = { api: { salvar_relatorio_pdf: salvar } };
        const mensagens = spyOn(fixture.debugElement.injector.get(MessageService), 'add');
        await component.salvar();
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'success', detail: 'PDF salvo com sucesso.' }));
        await component.salvar();
        expect(mensagens).toHaveBeenCalledTimes(1);
        await component.salvar();
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error', detail: 'Falha ao salvar' }));
    });

    it('gera novamente para todos os apartamentos após limpar a seleção', async () => {
        const consulta = jasmine.createSpy('get_relatorio_recebimentos').and.callFake(relatorio);
        window.pywebview = { api: { get_apartamentos: () => Promise.resolve({ status: 'success', data: ['101', '102'] }), get_relatorio_recebimentos: consulta } };
        component.relatorioSelecionado = 'extrato-recebimentos';
        await component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        const formulario = fixture.debugElement.query(By.directive(ExtratoRecebimentosComponent)).componentInstance as ExtratoRecebimentosComponent;
        formulario.apartamentosSelecionados = ['101'];
        fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        expect(consulta.calls.mostRecent().args[0].apartamentos).toEqual(['101']);

        const seletor = fixture.debugElement.query(By.directive(MultiSelect)).componentInstance as MultiSelect;
        seletor.clear(new MouseEvent('click'));
        fixture.detectChanges();
        expect(formulario.apartamentosSelecionados).toBeNull();
        fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        expect(consulta.calls.mostRecent().args[0].apartamentos).toEqual([]);
        expect(fixture.nativeElement.querySelector('.relatorio-impressao').textContent).toContain('Todos');
    });

    it('mostra erro e permite tentar novamente quando não consegue carregar apartamentos', async () => {
        window.pywebview = { api: { get_apartamentos: jasmine.createSpy().and.returnValues(
            Promise.resolve({ status: 'error', message: 'Falha na consulta' }),
            Promise.resolve({ status: 'success', data: ['301'] })
        ), get_relatorio_recebimentos: relatorio } };
        component.relatorioSelecionado = 'extrato-recebimentos';
        await component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain('Falha na consulta');
        (fixture.nativeElement.querySelector('button.text-primary') as HTMLButtonElement).click();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        fixture.detectChanges();
        const formulario = fixture.debugElement.query(By.directive(ExtratoRecebimentosComponent)).componentInstance as ExtratoRecebimentosComponent;
        expect(formulario.apartamentos).toEqual(['301']);
        expect(formulario.erroApartamentos).toBe('');
    });

    it('altera o tipo de período e limpa o intervalo anterior', async () => {
        component.relatorioSelecionado = 'extrato-recebimentos';
        await component.alterarRelatorio();
        fixture.changeDetectorRef.markForCheck();
        fixture.detectChanges();
        await fixture.whenStable();
        const formulario = fixture.debugElement.query(By.directive(ExtratoRecebimentosComponent)).componentInstance as ExtratoRecebimentosComponent;
        const competencia = fixture.nativeElement.querySelector('#tipo-extrato-competencia') as HTMLInputElement;
        competencia.click();
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        expect(formulario.tipo).toBe('competencia');
        expect((fixture.nativeElement.querySelector('#extrato-periodo') as HTMLInputElement).disabled).toBeFalse();
        formulario.periodo = [new Date(2026, 0, 1), new Date(2026, 1, 1)];
        (fixture.nativeElement.querySelector('#tipo-extrato-recebimento') as HTMLInputElement).click();
        fixture.detectChanges();
        expect(formulario.tipo).toBe('recebimento');
        expect(formulario.periodo).toBeNull();
    });

    it('busca e destaca termos com marcatexto amarelo no relatório e permite navegar entre resultados', async () => {
        component.extratoGerado = {
            data_corte: '2023-12-31',
            total: 200,
            apartamentos: [{
                apartamento: '101',
                subtotal: 200,
                competencias: [{
                    competencia: '2023-01',
                    subtotal: 200,
                    lancamentos: [
                        { id: 1, data: '2023-01-10', descricao: 'Taxa Ordinária Apto 101', tipo: 'Cobrança', valor: 100, desconto_vista: 0, renegociado: false },
                        { id: 2, data: '2023-01-10', descricao: 'Fundo Reserva Apto 101', tipo: 'Cobrança', valor: 100, desconto_vista: 0, renegociado: false }
                    ]
                }]
            }]
        };
        component.relatorioSelecionado = 'extrato-recebimentos';
        component.componenteRelatorio = ExtratoRecebimentosComponent;
        fixture.detectChanges();
        await fixture.whenStable();

        const campoBusca = fixture.nativeElement.querySelector('input[placeholder="Buscar no relatório..."]') as HTMLInputElement;
        expect(campoBusca).not.toBeNull();

        // Busca pelo termo "101"
        component.termoBusca = '101';
        component.executarBusca();
        fixture.detectChanges();

        expect(component.totalOcorrencias).toBeGreaterThanOrEqual(2);
        expect(component.indiceAtual).toBe(0);

        const marks = fixture.nativeElement.querySelectorAll('mark.relatorio-busca-termo');
        expect(marks.length).toBe(component.totalOcorrencias);
        expect(marks[0].classList.contains('relatorio-busca-ativo')).toBeTrue();

        // Avançar para próximo
        component.proximaOcorrencia();
        fixture.detectChanges();
        expect(component.indiceAtual).toBe(1);
        expect(marks[0].classList.contains('relatorio-busca-ativo')).toBeFalse();
        expect(marks[1].classList.contains('relatorio-busca-ativo')).toBeTrue();

        // Voltar para anterior
        component.anteriorOcorrencia();
        fixture.detectChanges();
        expect(component.indiceAtual).toBe(0);
        expect(marks[0].classList.contains('relatorio-busca-ativo')).toBeTrue();

        // Limpar busca
        component.limparBusca();
        fixture.detectChanges();
        expect(component.totalOcorrencias).toBe(0);
        expect(component.indiceAtual).toBe(-1);
        expect(fixture.nativeElement.querySelectorAll('mark.relatorio-busca-termo').length).toBe(0);
    });
});
