import { TestBed } from '@angular/core/testing';
import { ConfiguracoesComponent } from './configuracoes';

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

});
