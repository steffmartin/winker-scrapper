import { TestBed } from '@angular/core/testing';
import { LayoutService } from './layout.service';

describe('LayoutService', () => {
    let layout: LayoutService;
    beforeEach(() => {
        TestBed.configureTestingModule({ providers: [LayoutService] });
        layout = TestBed.inject(LayoutService);
    });
    afterEach(() => {
        document.documentElement.classList.remove('app-dark');
        delete window.pywebview;
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
});
