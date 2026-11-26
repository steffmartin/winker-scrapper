import { TestBed } from '@angular/core/testing';
import { ConfiguracoesComponent } from './configuracoes';
import { ConfirmationService } from 'primeng/api';

describe('Configurações financeiras', () => {
    afterEach(() => { delete window.pywebview; });

    it('carrega e salva a margem de encargos em reais', async () => {
        const salvar = jasmine.createSpy('atualizar').and.resolveTo({ status: 'success', message: 'Salvo' });
        window.pywebview = { api: {
            get_condominio_config: () => Promise.resolve({ status: 'success', data: {
                condominio: { nome: 'Condomínio', margem_diferenca_encargos: 0.15 }, membros: [], contas: []
            } }),
            update_condominio_config: salvar
        } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        expect(fixture.componentInstance.configForm.get('condominio.margem_diferenca_encargos')?.value).toBe(0.15);
        fixture.componentInstance.configForm.get('condominio.margem_diferenca_encargos')?.setValue(0.25);
        fixture.componentInstance.salvar();
        expect(salvar.calls.mostRecent().args[0].condominio.margem_diferenca_encargos).toBe(0.25);
        await fixture.whenStable();
        fixture.componentInstance.configForm.get('condominio.margem_diferenca_encargos')?.setValue(-0.01);
        expect(fixture.componentInstance.configForm.invalid).toBeTrue();
    });
    it('edita e reordena regras localmente, persistindo somente ao salvar', async () => {
        const regras = [
            { id: 1, descricao_contem: ' tarifa ', campo: 'fornecedor', valor: 'Banco' },
            { id: 2, descricao_contem: 'tarifa', campo: 'conta', valor: 'Corrente' }
        ];
        const salvar = jasmine.createSpy('atualizar').and.callFake((payload: any) => Promise.resolve({
            status: 'success', regras_preenchimento: payload.regras_preenchimento.map((regra: any, index: number) => ({ ...regra, id: index + 10 }))
        }));
        window.pywebview = { api: {
            get_condominio_config: () => Promise.resolve({ status: 'success', data: {
                condominio: { nome: 'Condomínio' }, membros: [], contas: [], regras_preenchimento: regras
            } }),
            update_condominio_config: salvar
        } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        const component = fixture.componentInstance;
        component.editarRegra(0, new Event('click'));
        component.regraForm.patchValue({ valor: 'Outro banco' });
        component.salvarRegra();
        component.iniciarArrasteRegra(0, new DragEvent('dragstart'));
        component.sobreRegra(1, new DragEvent('dragover'));
        expect([component.posicaoVisualRegra(0), component.posicaoVisualRegra(1)]).toEqual([1, 0]);
        expect(component.regras.value.map((r: any) => r.campo)).toEqual(['fornecedor', 'conta']);
        component.soltarRegra(0, new DragEvent('drop'));
        expect(component.regras.value.map((r: any) => r.campo)).toEqual(['conta', 'fornecedor']);
        expect(component.regras.at(1).value.descricao_contem).toBe(' tarifa ');
        expect(component.configForm.dirty).toBeTrue();
        expect(salvar).not.toHaveBeenCalled();
        component.salvar();
        expect(salvar.calls.mostRecent().args[0].regras_preenchimento.map((r: any) => r.campo)).toEqual(['conta', 'fornecedor']);
        await fixture.whenStable();
        expect(component.regras.value.map((r: any) => r.id)).toEqual([10, 11]);
        component.removerRegra(0, new Event('click'));
        expect(component.regras.length).toBe(1);
        expect(component.configForm.dirty).toBeTrue();
        component.showRegraDialog();
        component.regraForm.patchValue({ descricao_contem: ' ', valor: 'x' });
        expect(component.regraForm.invalid).toBeTrue();
        component.regraForm.patchValue({ descricao_contem: 'nova', campo: 'conta', valor: 'x' });
        component.salvarRegra();
        expect(component.regras.length).toBe(2);
        expect(salvar).toHaveBeenCalledTimes(1);
    });

    it('edita membros, telefones, apartamentos e contas sem gravar até salvar', async () => {
        const salvar = jasmine.createSpy().and.resolveTo({ status: 'success' });
        window.pywebview = { api: {
            get_condominio_config: () => Promise.resolve({ status: 'success', data: {
                condominio: { nome: 'Condomínio', telefone_administradora: ['1133334444'], apartamentos: ['101'] },
                membros: [{ nome: 'Ana', cargo: 'Síndico' }], contas: [{ conta: 'Corrente', saldo_inicial: 10 }]
            } }),
            update_condominio_config: salvar
        } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        const componente = fixture.componentInstance;
        componente.editarMembro(0);
        componente.novoMembroForm.patchValue({ nome: 'Beatriz', cargo: 'Conselheiro' });
        componente.salvarNovoMembro();
        componente.showDialog();
        componente.novoMembroForm.patchValue({ nome: 'Carlos', cargo: 'Síndico' });
        componente.salvarNovoMembro();
        componente.editarTelefone(0);
        expect(componente.novoTelefoneForm.value.numero).toBe('(11) 3333-4444');
        componente.novoTelefoneForm.patchValue({ numero: '(11) 99999-8888' });
        componente.salvarNovoTelefone();
        componente.showApartamentoDialog();
        componente.novoApartamentoForm.patchValue({ numero: '002' });
        componente.salvarNovoApartamento();
        componente.editarConta(0);
        componente.novoContaForm.patchValue({ conta: 'Reserva', saldo_inicial: 25 });
        componente.salvarNovaConta();
        expect(componente.membros.value.map((m: any) => m.nome)).toEqual(['Beatriz', 'Carlos']);
        expect(componente.telefones.value).toEqual(['11999998888']);
        expect(componente.apartamentos.value).toEqual(['101', '002']);
        expect(componente.contas.value[0]).toEqual({ conta: 'Reserva', saldo_inicial: 25 });
        expect(componente.getMembroIcon('Síndico')).toBe('pi pi-crown');
        expect(componente.formatarTelefone('11999998888')).toBe('(11) 99999-8888');
        expect(componente.configForm.dirty).toBeTrue();
        expect(salvar).not.toHaveBeenCalled();
        componente.salvar();
        expect(salvar.calls.mostRecent().args[0].condominio.apartamentos).toEqual(['101', '002']);
        await fixture.whenStable();
    });

    it('aplica máscara de telefone e limita a quantidade de dígitos', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const componente = TestBed.createComponent(ConfiguracoesComponent).componentInstance;
        for (const [valor, esperado] of [['1', '(1'], ['1133', '(11) 33'], ['1133334444', '(11) 3333-4444'],
                                        ['11999998888123', '(11) 99999-8888']]) {
            componente.onTelefoneInput({ target: { value: valor } });
            expect(componente.novoTelefoneForm.value.numero).toBe(esperado);
        }
    });

    it('remove itens de configuração após a animação e mantém alterações locais', async () => {
        window.pywebview = { api: { get_condominio_config: () => Promise.resolve({ status: 'success', data: {
            condominio: { nome: 'Condomínio', telefone_administradora: ['1133334444'], apartamentos: ['101'] },
            membros: [{ nome: 'Ana', cargo: 'Síndica' }], contas: [{ conta: 'Corrente', saldo_inicial: 10 }]
        } }) } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        const componente = fixture.componentInstance;
        componente.removeMembro(0);
        componente.removeTelefone(0);
        componente.removeApartamento(0);
        componente.removeConta(0);
        fixture.detectChanges(false);
        expect(componente.membros.length).toBe(1);
        await new Promise(resolve => setTimeout(resolve, 250));
        expect([componente.membros.length, componente.telefones.length, componente.apartamentos.length,
                componente.contas.length]).toEqual([0, 0, 0, 0]);
        expect(componente.configForm.dirty).toBeTrue();
    });

    it('pede confirmação ao sair com alterações e respeita rejeição', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        const componente = fixture.componentInstance;
        expect(componente.canDeactivate()).toBeTrue();
        componente.configForm.markAsDirty();
        const confirmacao = fixture.debugElement.injector.get(ConfirmationService);
        spyOn(confirmacao, 'confirm').and.callFake((opcoes: any) => { opcoes.reject(); return confirmacao; });
        expect(await componente.canDeactivate()).toBeFalse();
        const evento: any = {};
        componente.unloadNotification(evento);
        expect(evento.returnValue).toBeTrue();
        componente.isSaving = true;
        expect(componente.canDeactivate()).toBeTrue();
    });

    it('formata data ao salvar e mantém formulário alterado quando backend rejeita', async () => {
        const salvar = jasmine.createSpy().and.resolveTo({ status: 'error', message: 'Falha simulada' });
        window.pywebview = { api: { get_condominio_config: () => Promise.resolve({ status: 'success', data: {
            condominio: { nome: 'Condomínio', inadimplencia_data_corte: '31/01/2025' }, membros: [], contas: []
        } }), update_condominio_config: salvar } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        const componente = fixture.componentInstance;
        expect(componente.configForm.get('condominio.inadimplencia_data_corte')?.value).toEqual(new Date(2025, 0, 31));
        componente.configForm.get('condominio.inadimplencia_data_corte')?.setValue(new Date(2025, 1, 5));
        componente.configForm.markAsDirty();
        componente.salvar();
        expect(salvar.calls.mostRecent().args[0].condominio.inadimplencia_data_corte).toBe('05/02/2025');
        await Promise.resolve();
        expect(componente.configForm.dirty).toBeTrue();
        expect(componente.isSaving).toBeFalse();
    });

    it('cobre diálogos de apartamento e conta, incluindo edição e rótulos', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const componente = TestBed.createComponent(ConfiguracoesComponent).componentInstance;
        componente.showContaDialog();
        expect(componente.displayContaDialog).toBeTrue();
        expect(componente.editandoContaIndex).toBeNull();
        componente.novoContaForm.patchValue({ conta: 'Poupança', saldo_inicial: 50 });
        componente.salvarNovaConta();
        expect(componente.contas.length).toBe(1);
        componente.showContaDialog();
        componente.editarConta(0, new Event('click'));
        expect(componente.editandoContaIndex).toBe(0);
        componente.novoContaForm.patchValue({ conta: 'Reserva', saldo_inicial: 70 });
        componente.salvarNovaConta();
        expect(componente.contas.at(0).value).toEqual({ conta: 'Reserva', saldo_inicial: 70 });
        componente.showApartamentoDialog();
        componente.apartamentos.push((componente as any).fb.control('101'));
        componente.editarApartamento(0, new Event('click'));
        expect(componente.editandoApartamentoIndex).toBe(0);
        componente.novoApartamentoForm.patchValue({ numero: '202' });
        componente.salvarNovoApartamento();
        expect(componente.apartamentos.at(0).value).toBe('202');
        expect(componente.formatarContaLabel(null)).toBe('');
        expect(componente.formatarContaLabel({})).toBe('');
        expect(componente.formatarContaLabel({ conta: 'Corrente', saldo_inicial: 10 })).toContain('Corrente');
    });

    it('trata telefone vazio, novo cadastro e formatos alternativos', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const componente = TestBed.createComponent(ConfiguracoesComponent).componentInstance;
        componente.telefones.push((componente as any).fb.control(''));
        componente.editarTelefone(0);
        expect(componente.novoTelefoneForm.value.numero).toBe('');
        componente.telefones.at(0).setValue('11999998888');
        componente.editarTelefone(0);
        expect(componente.novoTelefoneForm.value.numero).toBe('(11) 99999-8888');
        componente.showTelefoneDialog();
        componente.novoTelefoneForm.patchValue({ numero: '(21) 98888-7777' });
        componente.salvarNovoTelefone();
        expect(componente.telefones.value).toContain('21988887777');
        componente.onTelefoneInput({ target: { value: '' } });
        expect(componente.novoTelefoneForm.value.numero).toBe('');
        expect(componente.formatarTelefone('')).toBe('');
        expect(componente.formatarTelefone('123')).toBe('123');
    });

    it('anima chips durante o arraste e cobre posições de reordenação', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        const componente = fixture.componentInstance;
        const fb = (componente as any).fb;
        componente.regras.push(fb.group({ descricao_contem: ['a', null], campo: ['fornecedor', null], valor: ['x', null] }));
        componente.regras.push(fb.group({ descricao_contem: ['b', null], campo: ['conta', null], valor: ['y', null] }));
        const container = document.createElement('div');
        const chip1 = document.createElement('p-chip');
        const chip2 = document.createElement('p-chip');
        container.appendChild(chip1);
        container.appendChild(chip2);
        document.body.appendChild(container);
        try {
            componente.iniciarArrasteRegra(1, { currentTarget: chip2, dataTransfer: null } as any);
            componente.sobreRegra(0, { currentTarget: chip1, preventDefault: () => {} } as any);
            expect([componente.posicaoVisualRegra(0), componente.posicaoVisualRegra(1)]).toEqual([1, 0]);
            componente.soltarRegra(0, { preventDefault: () => {} } as any);
            componente.sobreRegra(1, { preventDefault: () => {} } as any);
            componente.finalizarArrasteRegra();
        } finally {
            document.body.removeChild(container);
        }
    });

    it('ignora soltar regra sem origem ou no mesmo destino', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const componente = TestBed.createComponent(ConfiguracoesComponent).componentInstance;
        componente.soltarRegra(0, { preventDefault: () => {} } as any);
        componente.iniciarArrasteRegra(0, { currentTarget: null, dataTransfer: null } as any);
        componente.soltarRegra(0, { preventDefault: () => {} } as any);
        componente.finalizarArrasteRegra();
    });

    it('protege edição e remoção durante animação e cobre ícone de cargo vazio', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const componente = TestBed.createComponent(ConfiguracoesComponent).componentInstance;
        componente.membros.push((componente as any).fb.group({ nome: ['Ana', null], cargo: ['Síndica', null] }));
        componente.removendoMembroIndex = 0;
        componente.editarMembro(0, new Event('click'));
        expect(componente.editandoMembroIndex).toBeNull();
        componente.removendoMembroIndex = null;
        expect(componente.getMembroIcon('')).toBeUndefined();
        componente.editarMembro(0, new Event('click'));
        expect(componente.editandoMembroIndex).toBe(0);
        componente.removendoTelefoneIndex = 0;
        componente.telefones.push((componente as any).fb.control('11999998888'));
        componente.editarTelefone(0);
        expect(componente.editandoTelefoneIndex).toBeNull();
        componente.removendoTelefoneIndex = null;
        componente.removendoApartamentoIndex = 0;
        componente.apartamentos.push((componente as any).fb.control('101'));
        componente.editarApartamento(0);
        expect(componente.editandoApartamentoIndex).toBeNull();
        componente.removendoApartamentoIndex = null;
        componente.removendoContaIndex = 0;
        componente.contas.push((componente as any).fb.group({ conta: ['Corrente', null], saldo_inicial: [0, null] }));
        componente.editarConta(0);
        expect(componente.editandoContaIndex).toBeNull();
        componente.removendoContaIndex = null;
    });

    it('trata falha de carga e salvamento sem backend ou com rejeição', async () => {
        (window as any).pywebview = { api: {
            get_condominio_config: () => Promise.resolve({ status: 'error', message: 'sem config' }),
            update_condominio_config: () => Promise.reject(new Error('falha de rede'))
        } };
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        const componente = fixture.componentInstance;
        componente.loadData();
        await fixture.whenStable();
        expect(componente.loading).toBeFalse();
        componente.configForm.get('condominio.nome')?.setValue('Condomínio');
        componente.configForm.markAsDirty();
        componente.salvar();
        await fixture.whenStable();
        await new Promise(resolve => setTimeout(resolve, 0));
        expect(componente.isSaving).toBeFalse();
        expect(componente.loading).toBeFalse();

        delete (window as any).pywebview;
        componente.salvar();
        expect(componente.isSaving).toBeFalse();
        expect(componente.loading).toBeFalse();
    });

    it('valida formulário obrigatório antes de salvar', async () => {
        await TestBed.configureTestingModule({ imports: [ConfiguracoesComponent] }).compileComponents();
        const fixture = TestBed.createComponent(ConfiguracoesComponent);
        const componente = fixture.componentInstance;
        componente.configForm.get('condominio.nome')?.setValue('');
        componente.configForm.markAsDirty();
        componente.salvar();
        expect(componente.isSaving).toBeFalse();
        expect(componente.configForm.invalid).toBeTrue();
    });

});
