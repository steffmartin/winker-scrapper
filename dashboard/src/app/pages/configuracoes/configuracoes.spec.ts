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
});
