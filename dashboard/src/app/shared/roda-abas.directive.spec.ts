import { ElementRef } from '@angular/core';
import { RodaAbasDirective } from './roda-abas.directive';

describe('RodaAbasDirective', () => {
    it('percorre em ambos os sentidos e libera a página sem transbordamento', () => {
        const host = document.createElement('div');
        const conteudo = document.createElement('div');
        conteudo.className = 'p-tablist-content';
        host.appendChild(conteudo);
        Object.defineProperty(conteudo, 'scrollWidth', { configurable: true, value: 600 });
        Object.defineProperty(conteudo, 'clientWidth', { configurable: true, value: 200 });
        const diretiva = new RodaAbasDirective(new ElementRef(host));
        diretiva.ngAfterViewInit();
        const direita = new WheelEvent('wheel', { deltaY: 50, cancelable: true });
        host.dispatchEvent(direita);
        expect(conteudo.scrollLeft).toBe(50);
        expect(direita.defaultPrevented).toBeTrue();
        host.dispatchEvent(new WheelEvent('wheel', { deltaY: -30, cancelable: true }));
        expect(conteudo.scrollLeft).toBe(20);
        Object.defineProperty(conteudo, 'scrollWidth', { configurable: true, value: 200 });
        const semExcesso = new WheelEvent('wheel', { deltaY: 50, cancelable: true });
        host.dispatchEvent(semExcesso);
        expect(semExcesso.defaultPrevented).toBeFalse();
        diretiva.ngOnDestroy();
    });
});
