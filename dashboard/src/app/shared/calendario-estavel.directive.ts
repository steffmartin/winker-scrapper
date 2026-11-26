import { Directive, OnDestroy, Self } from '@angular/core';
import { DatePicker } from 'primeng/datepicker';

/** Mantém o intervalo aberto quando o diálogo muda de tamanho ou rola. */
@Directive({ selector: 'p-datepicker[appCalendarioEstavel]', standalone: true })
export class CalendarioEstavelDirective implements OnDestroy {
    private readonly redimensionarOriginal: () => void;
    private readonly vincularRolagemOriginal: () => void;
    private readonly desvincularRolagemOriginal: () => void;
    private readonly reposicionar = () => {
        if (this.calendario.overlayVisible) this.calendario.alignOverlay();
    };
    private readonly vincularRolagem = () => window.addEventListener('scroll', this.reposicionar, true);
    private readonly desvincularRolagem = () => window.removeEventListener('scroll', this.reposicionar, true);

    constructor(@Self() private calendario: DatePicker) {
        this.redimensionarOriginal = calendario.onWindowResize;
        this.vincularRolagemOriginal = calendario.bindScrollListener;
        this.desvincularRolagemOriginal = calendario.unbindScrollListener;
        calendario.onWindowResize = this.reposicionar;
        calendario.bindScrollListener = this.vincularRolagem;
        calendario.unbindScrollListener = this.desvincularRolagem;
    }
    ngOnDestroy() {
        this.desvincularRolagem();
        this.calendario.onWindowResize = this.redimensionarOriginal;
        this.calendario.bindScrollListener = this.vincularRolagemOriginal;
        this.calendario.unbindScrollListener = this.desvincularRolagemOriginal;
    }
}
