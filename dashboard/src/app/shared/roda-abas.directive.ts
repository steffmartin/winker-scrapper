import { AfterViewInit, Directive, ElementRef, OnDestroy } from '@angular/core';

/** Permite percorrer listas de abas com a roda sem capturar a rolagem da página nas extremidades. */
@Directive({ selector: 'p-tablist[appRodaAbas]', standalone: true })
export class RodaAbasDirective implements AfterViewInit, OnDestroy {
    private readonly aoRolar = (evento: WheelEvent) => {
        const conteudo = this.elemento.nativeElement.querySelector('.p-tablist-content') as HTMLElement | null;
        if (!conteudo || conteudo.scrollWidth <= conteudo.clientWidth) return;
        const delta = evento.deltaX || evento.deltaY;
        if (!delta) return;
        const anterior = conteudo.scrollLeft;
        const fator = evento.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16 : evento.deltaMode === WheelEvent.DOM_DELTA_PAGE ? conteudo.clientWidth : 1;
        conteudo.scrollLeft += delta * fator;
        if (conteudo.scrollLeft !== anterior) evento.preventDefault();
    };
    constructor(private elemento: ElementRef<HTMLElement>) {}
    ngAfterViewInit() { this.elemento.nativeElement.addEventListener('wheel', this.aoRolar, { passive: false }); }
    ngOnDestroy() { this.elemento.nativeElement.removeEventListener('wheel', this.aoRolar); }
}
