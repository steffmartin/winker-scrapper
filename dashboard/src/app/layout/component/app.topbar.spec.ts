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
        const reuse = component.router.routeReuseStrategy.shouldReuseRoute as any;
        expect(reuse({} as any, {} as any)).toBeFalse();
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

    function capturarReady() {
        const capturados: EventListener[] = [];
        const original = EventTarget.prototype.addEventListener;
        spyOn(EventTarget.prototype, 'addEventListener').and.callFake(function (this: EventTarget, type: string, listener: any, ...rest: any[]) {
            if (type === 'pywebviewready') { capturados.push(listener); return; }
            return original.call(this, type, listener, ...rest);
        });
        return capturados;
    }

    it('aguarda pywebview ou aplica fallback mock no timeout', async () => {
        jasmine.clock().install();
        capturarReady();
        try {
            delete (window as any).pywebview;
            component.loadCondoData();
            jasmine.clock().tick(1000);
            expect(component.condoName).toBe('Condomínio (Mock)');

            component.condoName = null;
            (window as any).pywebview = { api: {
                get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'Tardio' } }),
                get_pendencias_revisao_count: () => Promise.resolve({ status: 'success', data: { count: 4 } })
            } };
            component.loadCondoData();
            jasmine.clock().tick(1000);
            await Promise.resolve();
            await Promise.resolve();
            expect(component.condoName as string | null).toBe('Tardio');
            expect(component.pendenciasCount).toBe(4);
        } finally {
            jasmine.clock().uninstall();
        }
    });

    it('responde ao evento pywebviewready buscando dados na API', async () => {
        const capturados = capturarReady();
        delete (window as any).pywebview;
        component.loadCondoData();
        (window as any).pywebview = { api: {
            get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'Pronto' } }),
            get_pendencias_revisao_count: () => Promise.resolve({ status: 'success', data: { count: 2 } })
        } };
        capturados.forEach(cb => cb(new Event('pywebviewready')));
        await Promise.resolve();
        await Promise.resolve();
        expect(component.condoName as string | null).toBe('Pronto');
        expect(component.pendenciasCount).toBe(2);
    });

    it('varia nome e pendências do mock conforme condomínio e flag', async () => {
        jasmine.clock().install();
        try {
            delete (window as any).pywebview;
            (window as any).__mockHasInconsistencies = false;
            component.fetchFromApi();
            component.currentCondoId = '2';
            jasmine.clock().tick(500);
            expect(component.condoName as string | null).toBe('Edifício Beta (Mock)');
            expect(component.pendenciasCount).toBe(0);
            component.condoName = null;
            component.currentCondoId = '3';
            (window as any).__mockHasInconsistencies = true;
            component.fetchFromApi();
            jasmine.clock().tick(500);
            expect(component.condoName as string | null).toBe('Vila Gama (Mock)');
            expect(component.pendenciasCount).toBe(12);
        } finally {
            jasmine.clock().uninstall();
            delete (window as any).__mockHasInconsistencies;
        }
    });

    it('trata respostas parciais, rejeições e erro na API da topbar', async () => {
        (window as any).pywebview = { api: {
            get_nome_condominio: jasmine.createSpy().and.returnValues(
                Promise.resolve({ status: 'success', data: {} }),
                Promise.reject(new Error('rede'))
            ),
            get_pendencias_revisao_count: jasmine.createSpy().and.returnValues(
                Promise.resolve({ status: 'success', data: {} }),
                Promise.resolve({ status: 'success' })
            )
        } };
        const erro = spyOn(console, 'error');
        component.fetchFromApi();
        await Promise.resolve();
        await Promise.resolve();
        expect(component.condoName).toBeNull();
        expect(component.pendenciasCount).toBe(0);
        component.fetchFromApi();
        await Promise.resolve();
        await Promise.resolve();
        expect(erro).toHaveBeenCalled();
    });

    it('carrega condomínios no modo mock e executa comandos do menu', async () => {
        jasmine.clock().install();
        try {
            delete (window as any).pywebview;
            const menu = { toggle: jasmine.createSpy() };
            component.userMenu = menu;
            component.toggleUserMenu(new Event('click'));
            expect(component.userMenuItems[0].label).toBe('Carregando...');
            jasmine.clock().tick(500);
            expect(component.condominios.length).toBe(3);
            expect(component.userMenuItems[0].label).toBe('Condomínios');
            const sair = component.userMenuItems.find(i => i.label === 'Opções')?.items?.[0];
            expect(sair?.label).toBe('Sair');
            const fechar = spyOn(window, 'close');
            sair?.command?.({} as any);
            expect(fechar).toHaveBeenCalled();
        } finally {
            jasmine.clock().uninstall();
        }
    });

    it('troca de condomínio no modo mock recarrega a rota', () => {
        delete (window as any).pywebview;
        const navegar = spyOn(component.router, 'navigate').and.resolveTo(true);
        component.currentCondoId = '1';
        component.condominios = [{ id: '1', nome: 'A' }, { id: '9', nome: 'B' }];
        component.userMenuItems = [{ label: 'Condomínios', items: component.condominios.map(c => ({
            label: c.nome, command: () => component.changeCondo(c.id)
        })) } as any];
        component.buildUserMenu();
        const condoItem = component.userMenuItems[0].items?.find(i => i.label === 'B');
        condoItem?.command?.({} as any);
        expect(component.currentCondoId).toBe('9');
        expect(navegar).toHaveBeenCalled();
        const reuse = component.router.routeReuseStrategy.shouldReuseRoute as any;
        expect(reuse({} as any, {} as any)).toBeFalse();
        expect(component.router.onSameUrlNavigation).toBe('reload');
    });

    it('avisa quando o menu ainda não carregou e usa cache de condomínios', () => {
        const warn = spyOn(console, 'warn');
        component.userMenu = undefined;
        component.toggleUserMenu(new Event('click'));
        expect(warn).toHaveBeenCalled();
    });

    it('trata erro de status ao trocar de condomínio e saída sem api', async () => {
        const alerta = spyOn(window, 'alert');
        const fechar = spyOn(window, 'close');
        const alterar = jasmine.createSpy('set_condominio').and.resolveTo({ status: 'error', message: 'negado' });
        (window as any).pywebview = { api: {
            set_condominio: alterar,
            get_condominios: () => Promise.resolve({ status: 'error' }),
            get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'X' } }),
            get_pendencias_revisao_count: () => Promise.resolve({ status: 'success', data: { count: 1 } })
        } };
        component.userMenu = { toggle: jasmine.createSpy() };
        component.toggleUserMenu(new Event('click'));
        await Promise.resolve();
        await Promise.resolve();
        expect(component.userMenuItems.map(i => i.label)).toEqual(['Opções']);

        component.currentCondoId = '1';
        component.changeCondo('2');
        await Promise.resolve();
        await Promise.resolve();
        expect(alerta).toHaveBeenCalledWith('Erro interno ao trocar de condomínio: negado');

        delete (window as any).pywebview.api.exit_app;
        component.exitApp();
        expect(fechar).toHaveBeenCalled();
    });
});
