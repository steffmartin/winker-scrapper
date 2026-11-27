import { TestBed } from '@angular/core/testing';
import { ImportacaoComponent } from './importacao';
import { ImportacaoService } from './importacao.service';

describe('ImportacaoComponent', () => {
    let componente: ImportacaoComponent;
    let api: any;
    const dados = { user: 'teste', password: 'ficticia', wl: '', portal_index: 1, log_level: 'INFO', periodo: null, headless: true, no_wait: true };

    beforeEach(() => {
        api = {
            listar_configs_importacao: jasmine.createSpy().and.resolveTo({ status: 'success', data: ['teste.config'], selecionado: 'teste.config' }),
            carregar_config_importacao: jasmine.createSpy().and.resolveTo({ status: 'success', data: dados, condominio_id: 42 }),
            iniciar_importacao: jasmine.createSpy().and.resolveTo({ status: 'success' }),
            obter_estado_importacao: jasmine.createSpy().and.resolveTo({ status: 'success', data: { is_running: false, log: '', cursor: 0 } }),
            enviar_entrada_importacao: jasmine.createSpy().and.resolveTo({ status: 'success' })
        };
        (window as any).pywebview = { api };
        TestBed.configureTestingModule({ imports: [ImportacaoComponent] });
        componente = TestBed.createComponent(ImportacaoComponent).componentInstance;
    });
    afterEach(() => { delete (window as any).pywebview; });

    it('carrega o arquivo associado e grava somente ao iniciar', async () => {
        await componente.listar();
        expect(componente.form.getRawValue()).toEqual(dados);
        expect(api.iniciar_importacao).not.toHaveBeenCalled();
        await componente.iniciar();
        expect(api.iniciar_importacao).toHaveBeenCalledWith('teste.config', dados, 42);
    });

    it('converte competências entre o arquivo e os seletores de mês', async () => {
        api.carregar_config_importacao.and.resolveTo({ status: 'success', data: { ...dados, periodo: ['2024-12', '2025-01'] }, condominio_id: 42 });
        await componente.listar();
        expect(componente.form.controls.periodo.value).toEqual([new Date(2024, 11, 1), new Date(2025, 0, 1)]);
        await componente.iniciar();
        expect(api.iniciar_importacao).toHaveBeenCalledWith('teste.config', { ...dados, periodo: ['2024-12', '2025-01'] }, 42);
    });

    it('não inicia enquanto o intervalo está incompleto', async () => {
        await componente.listar();
        componente.form.controls.periodo.setValue([new Date(2024, 11, 1), null]);
        await componente.iniciar();
        expect(api.iniciar_importacao).not.toHaveBeenCalled();
        expect(componente.erro).toContain('início e o fim');
    });

    it('envia respostas ao processo e mostra erros de início', async () => {
        componente.entrada = '2';
        await componente.enviar();
        expect(api.enviar_entrada_importacao).toHaveBeenCalledWith('2');
        expect(componente.entrada).toBe('');
        await componente.listar();
        api.iniciar_importacao.and.resolveTo({ status: 'error', message: 'Execução em andamento' });
        await componente.iniciar();
        expect(componente.erro).toBe('Execução em andamento');
    });

    it('apresenta erros ao listar, carregar e enviar respostas', async () => {
        api.listar_configs_importacao.and.resolveTo({ status: 'error', message: 'Lista indisponível' });
        await componente.listar();
        expect(componente.erro).toBe('Lista indisponível');
        componente.arquivo = 'teste.config';
        api.carregar_config_importacao.and.resolveTo({ status: 'error', message: 'Arquivo inválido' });
        await componente.carregar();
        expect(componente.erro).toBe('Arquivo inválido');
        expect(componente.carregado).toBeFalse();
        api.enviar_entrada_importacao.and.resolveTo({ status: 'error', message: 'Processo encerrado' });
        await componente.enviar();
        expect(componente.erro).toBe('Processo encerrado');
    });

    it('informa falhas de conexão e não inicia com formulário inválido', async () => {
        api.listar_configs_importacao.and.rejectWith(new Error('falha'));
        await componente.listar();
        expect(componente.erro).toContain('listar');
        componente.arquivo = 'teste.config';
        api.carregar_config_importacao.and.rejectWith(new Error('falha'));
        await componente.carregar();
        expect(componente.erro).toContain('carregar');
        api.enviar_entrada_importacao.and.rejectWith(new Error('falha'));
        await componente.enviar();
        expect(componente.erro).toContain('enviar');
        await componente.iniciar();
        expect(api.iniciar_importacao).not.toHaveBeenCalled();
    });

    it('lida com arquivo não selecionado e falha de conexão ao iniciar', async () => {
        componente.arquivo = '';
        await componente.carregar();
        expect(api.carregar_config_importacao).not.toHaveBeenCalled();
        await componente.listar();
        api.iniciar_importacao.and.rejectWith(new Error('falha'));
        await componente.iniciar();
        expect(componente.erro).toContain('iniciar');
        expect(componente.iniciando).toBeFalse();
    });

    it('acompanha o fim do console, pausa ao rolar para cima e retoma ao voltar ao fim', () => {
        const fixture = TestBed.createComponent(ImportacaoComponent);
        fixture.detectChanges();
        const tela = fixture.componentInstance;
        const consoleEl = fixture.nativeElement.querySelector('pre') as HTMLElement;
        let altura = 500;
        let posicao = 0;
        Object.defineProperty(consoleEl, 'scrollHeight', { get: () => altura });
        Object.defineProperty(consoleEl, 'clientHeight', { value: 100 });
        Object.defineProperty(consoleEl, 'scrollTop', { get: () => posicao, set: (valor: number) => { posicao = valor; } });
        tela.acompanhamento.log.set('primeira linha');
        fixture.detectChanges();
        expect(consoleEl.scrollTop).toBe(500);

        consoleEl.scrollTop = 100;
        consoleEl.dispatchEvent(new Event('scroll'));
        altura = 700;
        tela.acompanhamento.log.set('primeira linha\nsegunda linha');
        fixture.detectChanges();
        expect(consoleEl.scrollTop).toBe(100);

        consoleEl.scrollTop = 600;
        consoleEl.dispatchEvent(new Event('scroll'));
        altura = 900;
        tela.acompanhamento.log.set('primeira linha\nsegunda linha\nterceira linha');
        fixture.detectChanges();
        expect(consoleEl.scrollTop).toBe(900);
    });

    it('mantém os cantos internos retos no grupo de entrada', () => {
        const fixture = TestBed.createComponent(ImportacaoComponent);
        fixture.detectChanges();
        const grupo = fixture.nativeElement.querySelector('p-inputgroup');
        const input = grupo.querySelector('input');
        const botao = grupo.querySelector('button');
        expect(input.style.borderTopRightRadius).toBe('0px');
        expect(input.style.borderBottomRightRadius).toBe('0px');
        expect(botao.style.borderTopLeftRadius).toBe('0px');
        expect(botao.style.borderBottomLeftRadius).toBe('0px');
        expect(botao.getAttribute('aria-label')).toBe('Enviar resposta');
    });
});
