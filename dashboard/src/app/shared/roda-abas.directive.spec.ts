import { ElementRef } from '@angular/core';
import { RodaAbasDirective } from './roda-abas.directive';

describe('RodaAbasDirective', () => {
    let host: HTMLElement;
    let conteudo: HTMLElement;
    let abas: HTMLElement;
    let diretiva: RodaAbasDirective;

    const montar = (larguraAbas: number) => {
        host = document.createElement('div');
        host.style.width = '200px';
        conteudo = document.createElement('div');
        conteudo.className = 'p-tablist-content';
        conteudo.style.overflowX = 'scroll';
        abas = document.createElement('div');
        abas.style.width = `${larguraAbas}px`;
        abas.style.height = '20px';
        conteudo.appendChild(abas);
        host.appendChild(conteudo);
        document.body.appendChild(host);
        diretiva = new RodaAbasDirective(new ElementRef(host));
        diretiva.ngAfterViewInit();
    };

    afterEach(() => {
        diretiva?.ngOnDestroy();
        host?.remove();
    });

    it('percorre em ambos os sentidos e libera a página sem transbordamento', () => {
        montar(2000);
        expect(conteudo.scrollWidth).toBeGreaterThan(conteudo.clientWidth);

        const direita = new WheelEvent('wheel', { deltaY: 50, cancelable: true });
        host.dispatchEvent(direita);
        expect(conteudo.scrollLeft).toBe(50);
        expect(direita.defaultPrevented).toBeTrue();

        host.dispatchEvent(new WheelEvent('wheel', { deltaY: -30, cancelable: true }));
        expect(conteudo.scrollLeft).toBe(20);

        abas.style.width = '100px';
        const semExcesso = new WheelEvent('wheel', { deltaY: 50, cancelable: true });
        host.dispatchEvent(semExcesso);
        expect(semExcesso.defaultPrevented).toBeFalse();
    });

    it('converte delta em linhas e ignora eventos sem delta', () => {
        montar(2000);
        host.dispatchEvent(new WheelEvent('wheel', { deltaY: 50, deltaMode: WheelEvent.DOM_DELTA_LINE, cancelable: true }));
        expect(conteudo.scrollLeft).toBe(800);
        const semDelta = new WheelEvent('wheel', { deltaY: 0, cancelable: true });
        host.dispatchEvent(semDelta);
        expect(semDelta.defaultPrevented).toBeFalse();
    });
});
