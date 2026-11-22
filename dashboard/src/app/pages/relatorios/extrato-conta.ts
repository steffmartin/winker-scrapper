import { ChangeDetectorRef, Component, EventEmitter, Input, OnDestroy, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { MultiSelectModule } from 'primeng/multiselect';

export interface ExtratoContaFiltros { periodo: (Date | null)[] | null; contas: string[]; }
export interface ExtratoContaResultado {
    periodo: [string, string];
    contas: { conta: string; saldo_anterior: number; subtotal: number; saldo_final: number; provisorio: boolean; meses: {
        mes: string; subtotal: number; dias: { data: string; subtotal: number; saldo_final: number; transacoes: {
            id: number; data: string; descricao: string; tipo: string; valor: number; saldo: number;
        }[] }[];
    }[] }[];
}
@Component({
    selector: 'app-extrato-conta', standalone: true,
    imports: [CommonModule, FormsModule, ButtonModule, DatePickerModule, MultiSelectModule],
    templateUrl: './extrato-conta.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown { background-color: var(--p-primary-color); color: var(--p-primary-contrast-color); border-color: var(--p-primary-color); }
        .tabela { width: 100%; table-layout: fixed; border-collapse: collapse; min-width: 42rem; }
        .tabela th, .tabela td { padding: .5rem; vertical-align: top; overflow-wrap: anywhere; }
        @media print { .tabela { min-width: 0; } }
    `]
})
export class ExtratoContaComponent implements OnInit, OnDestroy {
    @Input() modo: 'formulario' | 'resultado' = 'formulario';
    @Input() dados: ExtratoContaResultado | null = null;
    @Input() filtros: ExtratoContaFiltros | null = null;
    @Input() aoGerar?: (filtros: ExtratoContaFiltros) => void;
    @Output() gerar = new EventEmitter<ExtratoContaFiltros>();
    private readonly hoje = new Date();
    periodo: (Date | null)[] | null = [new Date(this.hoje.getFullYear(), this.hoje.getMonth(), 1), new Date(this.hoje)];
    contas: string[] = [];
    selecionadas: string[] | null = [];
    carregando = false;
    erro = '';
    private readonly aoConectar = () => { void this.carregar(); };
    constructor(private cdr: ChangeDetectorRef) {}
    ngOnInit() { if (this.modo === 'formulario') { window.addEventListener('pywebviewready', this.aoConectar); void this.carregar(); } }
    ngOnDestroy() { window.removeEventListener('pywebviewready', this.aoConectar); }
    async carregar() {
        if (!window.pywebview?.api) { this.erro = 'Não foi possível conectar ao aplicativo para carregar as contas.'; return; }
        this.carregando = true; this.erro = '';
        try {
            const resposta = await window.pywebview.api.get_contas_relatorio();
            if (resposta.status !== 'success' || !Array.isArray(resposta.data)) throw new Error(resposta.message || 'Não foi possível carregar as contas.');
            this.contas = resposta.data;
        } catch (erro) { this.erro = erro instanceof Error ? erro.message : 'Não foi possível carregar as contas.'; }
        finally { this.carregando = false; this.cdr.markForCheck(); }
    }
    gerarRelatorio() {
        const filtros = { periodo: this.periodo?.map(data => data ? new Date(data) : null) ?? null, contas: [...(this.selecionadas ?? [])] };
        this.gerar.emit(filtros); this.aoGerar?.(filtros);
    }
}
