import { Component, OnInit, Input, Output, EventEmitter, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { SelectModule } from 'primeng/select';
import { FormsModule } from '@angular/forms';
import { MessageService, ConfirmationService } from 'primeng/api';

declare global {
    interface Window {
        pywebview?: any;
    }
}

@Component({
    selector: 'app-taxa-dialog',
    standalone: true,
    imports: [
        CommonModule, ButtonModule, InputTextModule, InputNumberModule,
        DatePickerModule, DialogModule, SelectModule, FormsModule
    ],
    templateUrl: './taxa-dialog.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown {
            background-color: var(--p-primary-color) !important;
            color: var(--p-primary-contrast-color) !important;
            border-color: var(--p-primary-color) !important;
        }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown:hover {
            background-color: var(--p-primary-600) !important;
            border-color: var(--p-primary-600) !important;
        }
        :host ::ng-deep .primary-inputnumber-btn button.p-inputnumber-button {
            background-color: var(--p-primary-color) !important;
            color: var(--p-primary-contrast-color) !important;
            border-color: var(--p-primary-color) !important;
        }
        :host ::ng-deep .primary-inputnumber-btn button.p-inputnumber-button:hover {
            background-color: var(--p-primary-600) !important;
            border-color: var(--p-primary-600) !important;
        }
    `]
})
export class TaxaDialogComponent implements OnInit, OnChanges {
    @Input() visible: boolean = false;
    @Output() visibleChange = new EventEmitter<boolean>();
    
    @Input() taxaData?: any; // Se existir, é edição
    @Input() tipo: string = 'C'; // Para nova taxa
    @Input() autoFillApartamento?: string;
    @Input() autoFillCompetencia?: string; // YYYY-MM
    @Input() autoFillTaxaVinculadaId?: number;
    
    @Output() onSave = new EventEmitter<void>();
    @Output() onDelete = new EventEmitter<void>();

    isEdit: boolean = false;
    dialogTitle: string = '';
    currentTaxa: any = {};
    competenciaDate: Date | null = null;
    vencimentoDate: Date | null = null;
    mesesRepeticao: number = 1;
    taxasParaDesconto: any[] = [];
    apartamentos: string[] = [];

    constructor(
        private cdr: ChangeDetectorRef,
        private messageService: MessageService,
        private confirmationService: ConfirmationService
    ) {}

    ngOnInit() {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_condominio_config().then((res: any) => {
                if (res.status === 'success' && res.data && res.data.condominio && res.data.condominio.apartamentos) {
                    this.apartamentos = res.data.condominio.apartamentos;
                }
            });
        }
    }

    ngOnChanges(changes: SimpleChanges) {
        if (changes['visible'] && changes['visible'].currentValue) {
            this.initDialog();
        }
    }

    initDialog() {
        if (this.taxaData) {
            this.isEdit = true;
            this.dialogTitle = this.taxaData.tipo === 'C' ? 'Editar Taxa Comum' : (this.taxaData.tipo === 'E' ? 'Editar Taxa Extra' : (this.taxaData.tipo === 'D' ? 'Editar Desconto' : 'Editar Taxa Individual'));
            this.currentTaxa = { ...this.taxaData };
            
            if (this.taxaData.competencia) {
                const parts = this.taxaData.competencia.split('-');
                if (parts.length === 2) {
                    this.competenciaDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
                }
            }
            if (this.taxaData.vencimento) {
                const parts = this.taxaData.vencimento.split('/');
                if (parts.length === 3) {
                    this.vencimentoDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
                }
            }
        } else {
            this.isEdit = false;
            this.dialogTitle = this.tipo === 'C' ? 'Nova Taxa Comum' : (this.tipo === 'E' ? 'Nova Taxa Extra' : (this.tipo === 'D' ? 'Novo Desconto' : 'Nova Taxa Individual'));
            this.currentTaxa = {
                tipo: this.tipo,
                apartamento: this.autoFillApartamento || null,
                descricao: '',
                valor_original: 0,
                desconto_vista: 0,
                multa_percentual: 0,
                juros_mes_percentual: 0,
                taxa_id: this.autoFillTaxaVinculadaId || null
            };
            
            if (this.autoFillCompetencia) {
                const parts = this.autoFillCompetencia.split('-');
                if (parts.length === 2) {
                    this.competenciaDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
                }
            } else {
                this.competenciaDate = null;
            }
            this.vencimentoDate = null;
            this.mesesRepeticao = 1;
        }
        
        if (this.currentTaxa.tipo === 'D') {
            this.loadTaxasParaDesconto();
        }
    }

    closeDialog() {
        this.visible = false;
        this.visibleChange.emit(false);
    }

    loadTaxasParaDesconto() {
        if (this.currentTaxa.tipo !== 'D' || !this.currentTaxa.apartamento || !this.competenciaDate) {
            this.taxasParaDesconto = [];
            return;
        }
        const c = this.competenciaDate;
        const compStr = `${c.getFullYear()}-${String(c.getMonth() + 1).padStart(2, '0')}`;
        
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_taxas_por_apartamento(this.currentTaxa.apartamento, [compStr, compStr], ['C', 'I', 'E', 'P']).then((res: any) => {
                if (res.status === 'success') {
                    this.taxasParaDesconto = res.data;
                    this.cdr.detectChanges();
                }
            });
        }
    }

    onDescontoChange() {
        if (!this.autoFillTaxaVinculadaId) {
            this.currentTaxa.taxa_id = null;
        }
        this.taxasParaDesconto = [];
        this.loadTaxasParaDesconto();
    }

    getSelectedTaxa() {
        if (!this.currentTaxa.taxa_id || !this.taxasParaDesconto) return null;
        return this.taxasParaDesconto.find(t => t.id === this.currentTaxa.taxa_id);
    }

    saveTaxa() {
        if (!this.competenciaDate) {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha a competência.' });
            return;
        }
        if (!this.vencimentoDate && this.currentTaxa.tipo !== 'D') {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha a data de vencimento.' });
            return;
        }
        if (!this.currentTaxa.descricao || this.currentTaxa.descricao.trim() === '') {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha a descrição.' });
            return;
        }
        if (this.currentTaxa.valor_original == null) {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha o valor total.' });
            return;
        }
        if (this.currentTaxa.tipo === 'I' || this.currentTaxa.tipo === 'D') {
            if (!this.currentTaxa.apartamento || this.currentTaxa.apartamento.trim() === '') {
                this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha o apartamento.' });
                return;
            }
            if (!this.apartamentos.includes(this.currentTaxa.apartamento.trim()) && this.apartamentos.length > 0) {
                this.messageService.add({ severity: 'error', summary: 'Atenção', detail: `O apartamento ${this.currentTaxa.apartamento} não existe no condomínio.` });
                return;
            }
        }
        if (this.currentTaxa.tipo === 'D') {
            if (!this.currentTaxa.taxa_id) {
                this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Selecione a taxa referente ao desconto.' });
                return;
            }
            this.currentTaxa.valor_original = Math.abs(this.currentTaxa.valor_original || 0);
            this.currentTaxa.desconto_vista = Math.abs(this.currentTaxa.desconto_vista || 0);
            this.currentTaxa.multa_percentual = Math.abs(this.currentTaxa.multa_percentual || 0);
            this.currentTaxa.juros_mes_percentual = Math.abs(this.currentTaxa.juros_mes_percentual || 0);
            
            const taxaPai = this.taxasParaDesconto.find(t => t.id === this.currentTaxa.taxa_id);
            if (taxaPai) {
                if (this.currentTaxa.valor_original > taxaPai.valor_original || 
                    this.currentTaxa.desconto_vista > taxaPai.desconto_vista ||
                    this.currentTaxa.multa_percentual > taxaPai.multa_percentual ||
                    this.currentTaxa.juros_mes_percentual > taxaPai.juros_mes_percentual) {
                    this.messageService.add({ severity: 'error', summary: 'Atenção', detail: 'Os valores do desconto não podem ser maiores que os valores originais da taxa.' });
                    return;
                }
            }
        }
        
        this.currentTaxa.desconto_vista = this.currentTaxa.desconto_vista ?? 0;
        this.currentTaxa.multa_percentual = this.currentTaxa.multa_percentual ?? 0;
        this.currentTaxa.juros_mes_percentual = this.currentTaxa.juros_mes_percentual ?? 0;
        
        const c = this.competenciaDate as Date;
        const competencia = `${c.getFullYear()}-${String(c.getMonth() + 1).padStart(2, '0')}`;
        
        let vencimento = null;
        if (this.vencimentoDate) {
            const v = this.vencimentoDate;
            vencimento = `${String(v.getDate()).padStart(2, '0')}/${String(v.getMonth() + 1).padStart(2, '0')}/${v.getFullYear()}`;
        }
        
        const payload = {
            ...this.currentTaxa,
            competencia: competencia,
            vencimento: this.currentTaxa.tipo === 'D' ? null : vencimento,
            meses_repeticao: this.isEdit ? 1 : this.mesesRepeticao
        };
        
        if (window.pywebview && window.pywebview.api) {
            let action = this.isEdit ? 
                window.pywebview.api.update_taxa(this.currentTaxa.id, payload) : 
                window.pywebview.api.insert_taxa(payload);
                
            action.then((res: any) => {
                if (res.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro salvo com sucesso.' });
                    this.onSave.emit();
                    this.closeDialog();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        }
    }

    deleteTaxa() {
        if (this.currentTaxa.tipo === 'P' || this.currentTaxa.tipo === 'R') {
            this.messageService.add({ severity: 'error', summary: 'Erro', detail: 'Taxas de renegociação não podem ser excluídas individualmente. Exclua a renegociação inteira.' });
            return;
        }
        this.confirmationService.confirm({
            message: 'Tem certeza que deseja excluir esta taxa?',
            header: 'Confirmação',
            icon: 'pi pi-exclamation-triangle',
            acceptLabel: 'Sim',
            rejectLabel: 'Não',
            acceptButtonStyleClass: 'p-button-danger',
            rejectButtonStyleClass: 'p-button-secondary p-button-text',
            accept: () => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.delete_taxa(this.currentTaxa.id).then((res: any) => {
                        if (res.status === 'success') {
                            this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro excluído com sucesso.' });
                            this.onDelete.emit();
                            this.closeDialog();
                        } else {
                            this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                        }
                    });
                }
            }
        });
    }
}
