import { ChangeDetectorRef, Component, EventEmitter, Input, OnDestroy, OnInit, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { MultiSelectModule } from 'primeng/multiselect';
import { RadioButtonModule } from 'primeng/radiobutton';
import { CommonModule } from '@angular/common';

type TipoExtrato = 'completo' | 'competencia' | 'recebimento';

export interface ExtratoRecebimentosFiltros {
    tipo: TipoExtrato;
    periodo: (Date | null)[] | null;
    apartamentos: string[];
}
export interface ExtratoRecebimentosResultado {
    data_corte: string;
    total: number;
    limites?: { inicio: string; fim: string };
    apartamentos: { apartamento: string | null; subtotal: number; competencias: { competencia: string | null; subtotal: number; lancamentos: { id: number; data: string; descricao: string; tipo: string; valor: number; desconto_vista: number; renegociado: boolean }[] }[] }[];
}

@Component({
    selector: 'app-extrato-recebimentos',
    standalone: true,
    imports: [CommonModule, FormsModule, ButtonModule, DatePickerModule, MultiSelectModule, RadioButtonModule],
    templateUrl: './extrato-recebimentos.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown {
            background-color: var(--p-primary-color);
            color: var(--p-primary-contrast-color);
            border-color: var(--p-primary-color);
        }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown:hover {
            background-color: var(--p-primary-600);
            border-color: var(--p-primary-600);
        }
        .tabela-extrato { width: 100%; min-width: 44rem; table-layout: fixed; border-collapse: collapse; }
        .tabela-extrato th, .tabela-extrato td { padding: .5rem; vertical-align: top; overflow-wrap: anywhere; }
        .tabela-extrato .valor { text-align: right; white-space: nowrap; }
        .fim-competencia { border-bottom: 1px solid var(--surface-border); }
        @media print { .tabela-extrato { min-width: 0; } }
    `]
})
export class ExtratoRecebimentosComponent implements OnInit, OnDestroy {
    @Input() modo: 'formulario' | 'resultado' = 'formulario';
    @Input() dados: ExtratoRecebimentosResultado | null = null;
    @Input() filtrosGerados: ExtratoRecebimentosFiltros | null = null;
    @Input() aoGerar?: (filtros: ExtratoRecebimentosFiltros) => void;
    @Output() gerar = new EventEmitter<ExtratoRecebimentosFiltros>();

    tipo: TipoExtrato = 'completo';
    periodo: (Date | null)[] | null = null;
    apartamentosSelecionados: string[] | null = [];
    apartamentos: string[] = [];
    carregandoApartamentos = false;
    erroApartamentos = '';
    dataMinima: Date | undefined;
    dataMaxima: Date | undefined;
    private readonly aoConectar = () => { void this.carregarApartamentos(); };

    constructor(private cdr: ChangeDetectorRef) {}

    ngOnInit() {
        if (this.modo === 'formulario') {
            window.addEventListener('pywebviewready', this.aoConectar);
            void this.carregarApartamentos();
        }
    }

    ngOnDestroy() {
        window.removeEventListener('pywebviewready', this.aoConectar);
    }

    async carregarApartamentos() {
        const api = window.pywebview?.api;
        if (!api) {
            this.erroApartamentos = 'Não foi possível conectar ao aplicativo para carregar os apartamentos.';
            return;
        }
        this.carregandoApartamentos = true;
        this.erroApartamentos = '';
        try {
            const [resposta, limites] = await Promise.all([api.get_apartamentos(), api.get_relatorio_recebimentos({ limites: true })]);
            if (resposta.status !== 'success' || !Array.isArray(resposta.data) || !resposta.data.every((item: unknown) => typeof item === 'string')) {
                throw new Error(resposta.message || 'Resposta inválida ao carregar apartamentos.');
            }
            if (limites.status !== 'success') throw new Error(limites.message || 'Não foi possível carregar os limites do período.');
            this.apartamentos = resposta.data;
            this.dataMinima = this.dataLocal(limites.data.limites.inicio);
            this.dataMaxima = this.dataLocal(limites.data.limites.fim);
        } catch (erro) {
            this.erroApartamentos = erro instanceof Error ? erro.message : 'Não foi possível carregar os apartamentos.';
        } finally {
            this.carregandoApartamentos = false;
            this.cdr.markForCheck();
        }
    }
    private dataLocal(valor: string): Date {
        const [ano, mes, dia] = valor.split('-').map(Number);
        return new Date(ano, mes - 1, dia);
    }
    tipos: { valor: TipoExtrato; titulo: string; descricao: string }[] = [
        { valor: 'completo', titulo: 'Completo', descricao: 'Traz todos os recebimentos.' },
        { valor: 'competencia', titulo: 'Por competência', descricao: 'Filtra os recebimentos pela competência.' },
        { valor: 'recebimento', titulo: 'Por recebimento', descricao: 'Filtra os recebimentos pela data de compensação.' }
    ];

    alterarTipo() {
        this.periodo = null;
    }

    gerarRelatorio() {
        const filtros: ExtratoRecebimentosFiltros = {
            tipo: this.tipo,
            periodo: this.periodo?.map(data => data ? new Date(data) : null) ?? null,
            apartamentos: [...(this.apartamentosSelecionados ?? [])]
        };
        this.gerar.emit(filtros);
        this.aoGerar?.(filtros);
    }
}
