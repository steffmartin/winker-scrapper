import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { MessageModule } from 'primeng/message';

@Component({
    selector: 'app-dica-ordenacao',
    standalone: true,
    imports: [MessageModule],
    template: `@if (visivel()) {
        <p-message severity="info">Segure Ctrl e clique nos cabeçalhos para ordenar por mais de uma coluna.</p-message>
    }`,
    styles: [`
        :host { position: fixed; z-index: 1200; left: 50%; bottom: 4rem; transform: translateX(-50%); width: max-content; max-width: calc(100vw - 2rem); pointer-events: none; }
        :host([hidden]) { display: none; }
        p-message { pointer-events: auto; border: 1px solid var(--p-primary-color); outline: none; }
    `]
})
export class DicaOrdenacaoComponent implements OnInit, OnDestroy {
    visivel = signal(true);
    private temporizador?: ReturnType<typeof setTimeout>;
    ngOnInit() { this.temporizador = setTimeout(() => this.fechar(), 15000); }
    fechar() { this.visivel.set(false); if (this.temporizador) clearTimeout(this.temporizador); }
    ngOnDestroy() { if (this.temporizador) clearTimeout(this.temporizador); }
}
