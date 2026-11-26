import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { providePrimeNG } from 'primeng/config';
import { AppConfigurator } from './app.configurator';
import { LayoutService } from '../service/layout.service';

describe('Configuração de aparência', () => {
    beforeEach(() => TestBed.configureTestingModule({ imports: [AppConfigurator], providers: [provideRouter([]), providePrimeNG()] }));

    it('gera a paleta correspondente ao preset e à cor primária', () => {
        const componente = TestBed.createComponent(AppConfigurator).componentInstance;
        const layout = TestBed.inject(LayoutService);
        expect(componente.primaryColors().map(c => c.name)).toContain('blue');
        layout.layoutConfig.update(c => ({ ...c, primary: 'noir' }));
        expect(componente.getPresetExt().semantic.primary![500]).toBe('{surface.500}');
        layout.layoutConfig.update(c => ({ ...c, primary: 'blue', preset: 'Nora' }));
        expect(componente.getPresetExt().semantic.colorScheme.light.primary.color).toBe('{primary.600}');
        layout.layoutConfig.update(c => ({ ...c, preset: 'Aura' }));
        expect(componente.getPresetExt().semantic.colorScheme.light.primary.color).toBe('{primary.500}');
    });

    it('atualiza seleção de cor e modo do menu', () => {
        const componente = TestBed.createComponent(AppConfigurator).componentInstance;
        const aplicar = spyOn(componente, 'applyTheme');
        const evento = { stopPropagation: jasmine.createSpy() };
        const azul = { name: 'blue', palette: {} };
        componente.updateColors(evento, 'primary', azul);
        expect(componente.selectedPrimaryColor()).toBe('blue');
        expect(aplicar).toHaveBeenCalledWith('primary', azul);
        componente.updateColors(evento, 'surface', { name: 'slate', palette: {} });
        expect(componente.selectedSurfaceColor()).toBe('slate');
        componente.onMenuModeChange('overlay');
        expect(componente.menuMode()).toBe('overlay');
        expect(evento.stopPropagation).toHaveBeenCalledTimes(2);
    });
});
