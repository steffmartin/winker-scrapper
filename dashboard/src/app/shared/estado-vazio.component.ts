import { Component, Input } from '@angular/core';

/** Estado vazio compartilhado pelas telas do dashboard. */
@Component({
    selector: 'app-estado-vazio',
    standalone: true,
    styles: [':host { display: contents; }'],
    template: `
        <div [class]="classeFundo">
            <i [class]="icone + ' text-6xl ' + corIcone + ' mb-4'"></i>
            <h5 [class]="classeTitulo">{{ titulo }}</h5>
            <p [class]="classeDescricao">{{ descricao }}</p>
        </div>
    `
})
export class EstadoVazioComponent {
    @Input() titulo = '';
    @Input() descricao = '';
    @Input() icone = 'pi pi-check-circle';
    @Input() corIcone = 'text-green-500';
    @Input() tema: 'surface' | 'slate' = 'surface';

    get classeFundo(): string {
        const base = 'flex flex-col items-center justify-center p-8 text-center rounded-xl border my-4';
        return this.tema === 'slate'
            ? `${base} bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800`
            : `${base} bg-surface-50 dark:bg-surface-900 border-surface-200 dark:border-surface-800`;
    }

    get classeTitulo(): string {
        return this.tema === 'slate'
            ? 'text-xl font-bold text-slate-800 dark:text-slate-100 mb-2'
            : 'text-xl font-bold text-surface-800 dark:text-surface-100 mb-2';
    }

    get classeDescricao(): string {
        return this.tema === 'slate'
            ? 'text-slate-600 dark:text-slate-400'
            : 'text-surface-600 dark:text-surface-400';
    }
}
