import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AppMenuitem } from './app.menuitem';
import { LayoutService } from '../service/layout.service';

describe('AppMenuitem', () => {
    beforeEach(() => TestBed.configureTestingModule({ imports: [AppMenuitem], providers: [provideRouter([])] }));

    it('abre e fecha grupos, preservando o caminho pai', () => {
        const fixture = TestBed.createComponent(AppMenuitem);
        fixture.componentRef.setInput('item', { label: 'Grupo', path: '/filho', items: [{ label: 'Página' }] });
        fixture.componentRef.setInput('parentPath', '/pai');
        const item = fixture.componentInstance;
        const layout = TestBed.inject(LayoutService);
        expect(item.fullPath()).toBe('/pai/filho');
        item.itemClick(new MouseEvent('click'));
        expect(layout.layoutState().activePath).toBe('/pai/filho');
        expect(item.isActive()).toBeTrue();
        item.itemClick(new MouseEvent('click'));
        expect(layout.layoutState().activePath).toBe('/pai');
    });

    it('ignora itens desabilitados e executa comandos de itens ativos', () => {
        const fixture = TestBed.createComponent(AppMenuitem);
        const item = fixture.componentInstance;
        const layout = TestBed.inject(LayoutService);
        const comando = jasmine.createSpy();
        fixture.componentRef.setInput('item', { disabled: true, command: comando });
        const evento = new MouseEvent('click', { cancelable: true });
        item.itemClick(evento);
        expect(evento.defaultPrevented).toBeTrue();
        expect(comando).not.toHaveBeenCalled();
        layout.layoutState.update(state => ({ ...state, overlayMenuActive: true, mobileMenuActive: true }));
        fixture.componentRef.setInput('item', { command: comando });
        item.itemClick(new MouseEvent('click'));
        expect(comando).toHaveBeenCalledTimes(1);
        expect(layout.isSidebarActive()).toBeFalse();
    });

    it('ativa o grupo pai quando a rota do item corresponde', () => {
        const fixture = TestBed.createComponent(AppMenuitem);
        fixture.componentRef.setInput('item', { routerLink: ['/revisao'] });
        fixture.componentRef.setInput('parentPath', '/operacoes');
        spyOn(TestBed.inject(Router), 'isActive').and.returnValue(true);
        fixture.componentInstance.updateActiveStateFromRoute();
        expect(TestBed.inject(LayoutService).layoutState().activePath).toBe('/operacoes');
    });
});
