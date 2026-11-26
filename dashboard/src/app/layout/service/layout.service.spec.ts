import { TestBed } from '@angular/core/testing';
import { LayoutService } from './layout.service';

describe('LayoutService', () => {
    let layout: LayoutService;
    beforeEach(() => {
        (document as any).startViewTransition = (cb: () => void) => { cb(); return { finished: Promise.resolve() }; };
        TestBed.configureTestingModule({ providers: [LayoutService] });
        layout = TestBed.inject(LayoutService);
    });
    afterEach(() => {
        document.documentElement.classList.remove('app-dark');
        delete window.pywebview;
        delete (document as any).startViewTransition;
    });

    it('alterna o menu de desktop e de dispositivo móvel', () => {
        spyOn(layout, 'isDesktop').and.returnValue(true);
        expect(layout.layoutState().staticMenuDesktopInactive).toBeTrue();
        layout.onMenuToggle();
        expect(layout.layoutState().staticMenuDesktopInactive).toBeFalse();
        (layout.isDesktop as jasmine.Spy).and.returnValue(false);
        layout.onMenuToggle();
        expect(layout.layoutState().mobileMenuActive).toBeTrue();
        expect(layout.isSidebarActive()).toBeTrue();
        layout.showConfigSidebar();
        expect(layout.layoutState().configSidebarVisible).toBeTrue();
        layout.hideConfigSidebar();
        expect(layout.layoutState().configSidebarVisible).toBeFalse();
    });

    it('mantém o modo overlay e o tema coerentes com a configuração', () => {
        layout.layoutConfig.update(config => ({ ...config, menuMode: 'overlay', darkTheme: true }));
        spyOn(layout, 'isDesktop').and.returnValue(true);
        layout.onMenuToggle();
        expect(layout.isOverlay()).toBeTrue();
        expect(layout.isSidebarActive()).toBeTrue();
        expect(layout.isDarkTheme()).toBeTrue();
        layout.toggleDarkMode();
        expect(document.documentElement.classList.contains('app-dark')).toBeTrue();
        layout.toggleDarkMode({ ...layout.layoutConfig(), darkTheme: false });
        expect(document.documentElement.classList.contains('app-dark')).toBeFalse();
    });

    it('expõe computados, dimensões e alterna o tema', () => {
        expect(layout.theme()).toBe('dark');
        expect(layout.getPrimary()).toBe('emerald');
        expect(layout.getSurface()).toBeNull();
        expect(layout.isMobile()).toBe(!layout.isDesktop());
        layout.layoutConfig.update(config => ({ ...config, darkTheme: true, surface: '#ffffff' }));
        expect(layout.theme()).toBe('light');
        expect(layout.isDarkTheme()).toBeTrue();
        expect(layout.getSurface()).toBe('#ffffff');
        layout.toggleDarkMode();
        expect(document.documentElement.classList.contains('app-dark')).toBeTrue();
        layout.toggleDarkMode({ preset: 'x', primary: 'y', surface: null, darkTheme: false, menuMode: 'static' });
        expect(document.documentElement.classList.contains('app-dark')).toBeFalse();
    });

    it('sincroniza preferências com o backend somente quando a API existe', () => {
        const sync = jasmine.createSpy('sync_preferencias_cache');
        window.pywebview = { api: { sync_preferencias_cache: sync } };
        layout.layoutConfig.update(config => ({ ...config, primary: 'blue' }));
        TestBed.tick();
        expect(sync).toHaveBeenCalled();

        window.pywebview = { api: {} };
        layout.layoutConfig.update(config => ({ ...config, primary: 'red' }));
        TestBed.tick();
        window.pywebview = {};
        layout.layoutConfig.update(config => ({ ...config, primary: 'green' }));
        TestBed.tick();
        expect(sync).toHaveBeenCalledTimes(1);
    });

    it('aplica transição de tema com view transition, fallback e erro', () => {
        const proto = Document.prototype as any;
        const originalProto = proto.startViewTransition;
        const originalDoc = (document as any).startViewTransition;
        const temClasse = () => document.documentElement.classList.contains('app-dark');
        try {
            layout.layoutConfig.update(config => ({ ...config }));
            TestBed.tick();
            (document as any).startViewTransition = (cb: () => void) => { cb(); return { finished: Promise.resolve() }; };
            layout.layoutConfig.update(config => ({ ...config, darkTheme: true }));
            TestBed.tick();
            expect(temClasse()).toBeTrue();
            (document as any).startViewTransition = () => { throw new Error('sem suporte'); };
            layout.layoutConfig.update(config => ({ ...config, darkTheme: false }));
            TestBed.tick();
            expect(temClasse()).toBeFalse();
            delete (document as any).startViewTransition;
            delete proto.startViewTransition;
            layout.layoutConfig.update(config => ({ ...config, darkTheme: true }));
            TestBed.tick();
            expect(temClasse()).toBeTrue();
        } finally {
            delete (document as any).startViewTransition;
            if (originalDoc !== undefined) (document as any).startViewTransition = originalDoc;
            if (originalProto !== undefined) proto.startViewTransition = originalProto;
            else delete proto.startViewTransition;
        }
    });
});
