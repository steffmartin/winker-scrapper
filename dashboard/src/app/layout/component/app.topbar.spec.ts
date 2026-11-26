import { TestBed } from '@angular/core/testing';
import { AppTopbar } from './app.topbar';
import { ChangeDetectorRef } from '@angular/core';
import { LayoutService } from '@/app/layout/service/layout.service';
describe('AppTopbar', () => {
    let component: AppTopbar;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [
                LayoutService,
                { provide: ChangeDetectorRef, useValue: { detectChanges: () => {} } }
            ]
        });
        
        TestBed.runInInjectionContext(() => {
            component = new AppTopbar();
        });
    });

    afterEach(() => {
        delete (window as any).pywebview;
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should load condo data and inconsistencies from pywebview when available', async () => {
        (window as any).pywebview = {
            api: {
                get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'Condominio Pywebview' } }),
                get_pendencias_revisao_count: () => Promise.resolve({ status: 'success', data: { count: 5, details: { lancamentos: 5, categorias: 0, subcategorias: 0, meses: 0, documentos: 0 } } })
            }
        };

        component.loadCondoData();
        
        // Wait for promise resolution
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(component.condoName).toBe('Condominio Pywebview');
        expect(component.pendenciasCount).toBe(5);
    });

    it('carrega o menu de condomínios e troca a seleção usando o backend', async () => {
        const alterar = jasmine.createSpy().and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: {
            get_condominios: jasmine.createSpy().and.resolveTo({ status: 'success', current_id: '1',
                data: [{ id: '1', nome: 'Primeiro' }, { id: '2', nome: 'Segundo' }] }),
            set_condominio: alterar,
            get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'Segundo' } }),
            get_pendencias_revisao_count: () => Promise.resolve({ status: 'success', data: { count: 3 } })
        } };
        component.userMenu = { toggle: jasmine.createSpy() };
        const navegar = spyOn(component.router, 'navigate').and.resolveTo(true);
        component.toggleUserMenu(new Event('click'));
        await Promise.resolve();
        expect(component.userMenuItems[0].items?.map(i => i.label)).toEqual(['Primeiro', 'Segundo']);
        component.changeCondo('1');
        expect(alterar).not.toHaveBeenCalled();
        component.changeCondo('2');
        await Promise.resolve();
        await Promise.resolve();
        expect(alterar).toHaveBeenCalledOnceWith('2');
        expect(component.currentCondoId).toBe('2');
        expect(component.condominios).toEqual([]);
        expect(component.condoName).toBe('Segundo');
        expect(navegar).toHaveBeenCalled();
    });

    it('alterna tema, executa saída e encerra a assinatura de revisão', () => {
        const sair = jasmine.createSpy();
        (window as any).pywebview = { api: { exit_app: sair,
            get_nome_condominio: () => Promise.resolve({ status: 'error' }),
            get_pendencias_revisao_count: () => Promise.resolve({ status: 'error' }) } };
        const carregar = spyOn(component, 'fetchFromApi');
        component.ngOnInit();
        expect(carregar).toHaveBeenCalledTimes(1);
        component.layoutService.onReviewSaved.next();
        expect(carregar).toHaveBeenCalledTimes(2);
        component.ngOnDestroy();
        component.layoutService.onReviewSaved.next();
        expect(carregar).toHaveBeenCalledTimes(2);
        const anterior = component.layoutService.layoutConfig().darkTheme;
        component.toggleDarkMode();
        expect(component.layoutService.layoutConfig().darkTheme).toBe(!anterior);
        component.exitApp();
        expect(sair).toHaveBeenCalledOnceWith();
    });

    it('apresenta menu sem condomínios quando a consulta falha', async () => {
        const consulta = jasmine.createSpy().and.rejectWith(new Error('falha simulada'));
        (window as any).pywebview = { api: { get_condominios: consulta } };
        const menu = { toggle: jasmine.createSpy() };
        component.userMenu = menu;
        component.toggleUserMenu(new Event('click'));
        expect(component.userMenuItems[0].label).toBe('Carregando...');
        await Promise.resolve();
        await Promise.resolve();
        expect(component.userMenuItems.map(item => item.label)).toEqual(['Opções']);
        expect(component.userMenuItems[0].items?.[0].label).toBe('Sair');
        expect(menu.toggle).toHaveBeenCalledTimes(1);
    });

    it('usa dados em cache para reabrir menu sem consultar novamente', () => {
        const consulta = jasmine.createSpy();
        (window as any).pywebview = { api: { get_condominios: consulta } };
        const menu = { toggle: jasmine.createSpy() };
        component.userMenu = menu;
        component.condominios = [{ id: '1', nome: 'Primeiro' }];
        component.toggleUserMenu(new Event('click'));
        expect(menu.toggle).toHaveBeenCalledTimes(1);
        expect(consulta).not.toHaveBeenCalled();
    });

    it('limpa contagem quando o backend retorna erro e mantém nome anterior', async () => {
        component.condoName = 'Condomínio anterior';
        component.pendenciasCount = 5;
        (window as any).pywebview = { api: {
            get_nome_condominio: () => Promise.resolve({ status: 'error' }),
            get_pendencias_revisao_count: () => Promise.resolve({ status: 'error' })
        } };
        component.fetchFromApi();
        await Promise.resolve();
        expect(component.condoName).toBe('Condomínio anterior');
        expect(component.pendenciasCount).toBe(0);
    });
});
