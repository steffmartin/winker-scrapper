import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { TabsModule } from 'primeng/tabs';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { DatePickerModule } from 'primeng/datepicker';
import { InputMaskModule } from 'primeng/inputmask';
import { DialogModule } from 'primeng/dialog';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ToastModule } from 'primeng/toast';
import { AvatarModule } from 'primeng/avatar';
import { FormsModule } from '@angular/forms';
import { MessageService, ConfirmationService } from 'primeng/api';

@Component({
    selector: 'app-cobrancas',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        InputTextModule, InputNumberModule, DatePickerModule, InputMaskModule,
        DialogModule, ConfirmDialogModule, ToastModule, AvatarModule, FormsModule
    ],
    providers: [MessageService, ConfirmationService],
    templateUrl: './cobrancas.html',
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
        :host ::ng-deep .p-paginator {
            padding-top: 1rem !important;
        }
        :host ::ng-deep .p-tabs-list {
            margin-bottom: 1rem;
        }
        :host ::ng-deep .p-tabpanels {
            padding: 0 !important;
        }
    `]
})
export class CobrancasComponent implements OnInit {
    activeTab: string = 'comuns';
    taxas: any[] = [];
    loading: boolean = false;
    
    displayDialog: boolean = false;
    isEdit: boolean = false;
    dialogTitle: string = '';
    currentTaxa: any = {};
    
    competenciaDate: Date | null = null;
    vencimentoDate: Date | null = null;
    mesesRepeticao: number = 1;

    constructor(
        private cdr: ChangeDetectorRef,
        private messageService: MessageService,
        private confirmationService: ConfirmationService
    ) {}

    ngOnInit() {
        this.loadTaxas();
    }

    onTabChange(event: any) {
        this.activeTab = event;
    }

    loadTaxas() {
        this.loading = true;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_taxas_ordinarias().then((res: any) => {
                this.loading = false;
                if (res.status === 'success') {
                    this.taxas = res.data.map((t: any) => {
                        if (t.vencimento) {
                            const parts = t.vencimento.split('/');
                            if (parts.length === 3) {
                                t.vencimento_sort = `${parts[2]}-${parts[1]}-${parts[0]}`;
                            }
                        }
                        t.valor_a_vista = (t.valor_original || 0) - (t.desconto_vista || 0);
                        return t;
                    });
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
                this.cdr.detectChanges();
            }).catch(() => {
                this.loading = false;
                this.cdr.detectChanges();
            });
        } else {
            this.loading = false;
            if (window.location.hostname === 'localhost') {
                this.taxas = [
                    { id: 1, competencia: '2026-07', exibicao: 'JUL/2026', vencimento: '14/07/2026', descricao: 'Taxa Ordinária', valor_original: 1500, desconto_vista: 0, multa_atraso: 0, juros_dia_atraso: 0 }
                ];
            }
        }
    }

    addTaxa() {
        this.isEdit = false;
        this.dialogTitle = 'Nova Taxa Comum';
        this.currentTaxa = {
            descricao: '',
            valor_original: 0,
            desconto_vista: 0,
            multa_atraso: 0,
            juros_dia_atraso: 0
        };
        this.competenciaDate = null;
        this.vencimentoDate = null;
        this.mesesRepeticao = 1;
        this.displayDialog = true;
    }

    editTaxa(taxa: any) {
        this.isEdit = true;
        this.dialogTitle = 'Editar Taxa Comum';
        this.currentTaxa = { ...taxa };
        
        // Converter competencia de YYYY-MM para Date
        if (taxa.competencia) {
            const parts = taxa.competencia.split('-');
            if (parts.length === 2) {
                this.competenciaDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
            }
        }
        
        // Converter vencimento string DD/MM/YYYY para Date
        if (taxa.vencimento) {
            const parts = taxa.vencimento.split('/');
            if (parts.length === 3) {
                this.vencimentoDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
            }
        }
        
        this.displayDialog = true;
    }

    saveTaxa() {
        if (!this.competenciaDate) {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha a competência.' });
            return;
        }
        
        if (!this.vencimentoDate) {
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
        
        this.currentTaxa.desconto_vista = this.currentTaxa.desconto_vista ?? 0;
        this.currentTaxa.multa_atraso = this.currentTaxa.multa_atraso ?? 0;
        this.currentTaxa.juros_dia_atraso = this.currentTaxa.juros_dia_atraso ?? 0;
        
        const c = this.competenciaDate;
        const competencia = `${c.getFullYear()}-${String(c.getMonth() + 1).padStart(2, '0')}`;
        
        const v = this.vencimentoDate;
        const vencimento = `${String(v.getDate()).padStart(2, '0')}/${String(v.getMonth() + 1).padStart(2, '0')}/${v.getFullYear()}`;
        
        const payload = {
            ...this.currentTaxa,
            competencia: competencia,
            vencimento: vencimento,
            meses_repeticao: this.isEdit ? 1 : this.mesesRepeticao
        };
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            let action = this.isEdit ? 
                pywebview.api.update_taxa_ordinaria(this.currentTaxa.id, payload) : 
                pywebview.api.insert_taxa_ordinaria(payload);
                
            action.then((res: any) => {
                if (res.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro salvo com sucesso.' });
                    this.displayDialog = false;
                    this.loadTaxas();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        } else {
            // Mock
            this.displayDialog = false;
            this.loadTaxas();
        }
    }

    deleteTaxa() {
        this.confirmationService.confirm({
            message: 'Tem certeza que deseja excluir esta taxa?',
            header: 'Confirmação',
            icon: 'pi pi-exclamation-triangle',
            acceptLabel: 'Sim',
            rejectLabel: 'Não',
            acceptButtonStyleClass: 'p-button-danger',
            rejectButtonStyleClass: 'p-button-secondary p-button-text',
            accept: () => {
                const pywebview = (window as any).pywebview;
                if (pywebview && pywebview.api) {
                    pywebview.api.delete_taxa_ordinaria(this.currentTaxa.id).then((res: any) => {
                        if (res.status === 'success') {
                            this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro excluído com sucesso.' });
                            this.displayDialog = false;
                            this.loadTaxas();
                        } else {
                            this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                        }
                    });
                }
            }
        });
    }

    getAvatarColor(mesCompetencia: string): string {
        if (!mesCompetencia) return '#cbd5e1';
        const colors = ['#f87171', '#fb923c', '#fbbf24', '#a3e635', '#4ade80', '#2dd4bf', '#38bdf8', '#818cf8', '#a78bfa', '#e879f9', '#f43f5e', '#64748b'];
        const monthStr = mesCompetencia.split('-')[1];
        if (!monthStr) return '#cbd5e1';
        const month = parseInt(monthStr, 10);
        return colors[(month - 1) % colors.length];
    }
    
    getAvatarLabelMes(mesCompetencia: string): string {
        if (!mesCompetencia) return '';
        const monthStr = mesCompetencia.split('-')[1];
        if (!monthStr) return '';
        return monthStr;
    }
}
