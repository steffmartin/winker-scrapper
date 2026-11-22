import { ChangeDetectorRef, Component, EventEmitter, Input, OnDestroy, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { MultiSelectModule } from 'primeng/multiselect';

export interface InadimplenciaFiltros { data_corte: Date | null; apartamentos: string[]; }
export interface InadimplenciaResultado {
    data_corte: string;
    total: number;
    apartamentos: { apartamento: string; subtotal: number; competencias: { competencia: string | null; subtotal: number; taxas: { id: number; vencimento: string; descricao: string; valor: number }[] }[] }[];
}

@Component({
    selector: 'app-relatorio-inadimplencia', standalone: true,
    imports: [CommonModule, FormsModule, ButtonModule, DatePickerModule, MultiSelectModule],
    templateUrl: './relatorio-inadimplencia.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown { background-color: var(--p-primary-color); color: var(--p-primary-contrast-color); border-color: var(--p-primary-color); }
        .tabela { width: 100%; table-layout: fixed; border-collapse: collapse; }
        .tabela th, .tabela td { padding: .5rem; vertical-align: top; overflow-wrap: anywhere; }
        .fim-competencia { border-bottom: 1px solid var(--surface-border); }
    `]
})
export class RelatorioInadimplenciaComponent implements OnInit, OnDestroy {
    @Input() modo: 'formulario' | 'resultado' = 'formulario';
    @Input() dados: InadimplenciaResultado | null = null;
    @Input() filtros: InadimplenciaFiltros | null = null;
    @Input() aoGerar?: (filtros: InadimplenciaFiltros) => void;
    @Output() gerar = new EventEmitter<InadimplenciaFiltros>();
    dataCorte: Date | null = new Date();
    hoje = new Date();
    apartamentos: string[] = [];
    selecionados: string[] | null = [];
    carregando = false;
    erro = '';
    private readonly aoConectar = () => { void this.carregar(); };
    constructor(private cdr: ChangeDetectorRef) {}
    ngOnInit() {
        if (this.modo === 'formulario') {
            window.addEventListener('pywebviewready', this.aoConectar);
            void this.carregar();
        }
    }
    ngOnDestroy() { window.removeEventListener('pywebviewready', this.aoConectar); }
    async carregar() {
        if (!window.pywebview?.api) { this.erro = 'Não foi possível conectar ao aplicativo para carregar os apartamentos.'; return; }
        this.carregando = true;
        this.erro = '';
        try {
            const resposta = await window.pywebview.api.get_apartamentos();
            if (resposta.status !== 'success' || !Array.isArray(resposta.data)) throw new Error(resposta.message || 'Não foi possível carregar os apartamentos.');
            this.apartamentos = resposta.data;
        } catch (erro) {
            this.erro = erro instanceof Error ? erro.message : 'Não foi possível carregar os apartamentos.';
        } finally { this.carregando = false; this.cdr.markForCheck(); }
    }
    gerarRelatorio() {
        const filtros = { data_corte: this.dataCorte ? new Date(this.dataCorte) : null, apartamentos: [...(this.selecionados ?? [])] };
        this.gerar.emit(filtros);
        this.aoGerar?.(filtros);
    }
}
