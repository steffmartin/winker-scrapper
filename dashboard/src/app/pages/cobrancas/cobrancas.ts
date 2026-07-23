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
import { SelectModule } from 'primeng/select';
import { SpeedDialModule } from 'primeng/speeddial';
import { TooltipModule } from 'primeng/tooltip';
import { FormsModule } from '@angular/forms';
import { MessageService, ConfirmationService, MenuItem } from 'primeng/api';

@Component({
    selector: 'app-cobrancas',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        InputTextModule, InputNumberModule, DatePickerModule, InputMaskModule,
        DialogModule, ConfirmDialogModule, ToastModule, AvatarModule, SpeedDialModule, SelectModule, TooltipModule, FormsModule
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
        :host ::ng-deep .p-speeddial-action {
            background-color: var(--p-primary-color) !important;
            color: var(--p-primary-contrast-color) !important;
        }
        :host ::ng-deep .p-speeddial-action:hover {
            background-color: var(--p-primary-600) !important;
        }
    `]
})
export class CobrancasComponent implements OnInit {
    activeTab: string = 'comuns';
    taxasComuns: any[] = [];
    taxasIndividuais: any[] = [];
    loadingComuns: boolean = false;
    loadingIndividuais: boolean = false;
    taxasIndividuaisLoaded: boolean = false;
    apartamentos: string[] = [];
    speedDialItems: MenuItem[] = [];
    speedDialComunsItems: MenuItem[] = [];
    
    displayDialog: boolean = false;
    isEdit: boolean = false;
    dialogTitle: string = '';
    currentTaxa: any = {};
    
    competenciaDate: Date | null = null;
    vencimentoDate: Date | null = null;
    mesesRepeticao: number = 1;
    taxasParaDesconto: any[] = [];

    constructor(
        private cdr: ChangeDetectorRef,
        private messageService: MessageService,
        private confirmationService: ConfirmationService
    ) {}

    ngOnInit() {
        this.speedDialComunsItems = [
            {
                icon: 'pi pi-users',
                label: 'Nova Taxa Comum',
                tooltipOptions: { tooltipLabel: 'Nova Taxa Comum', tooltipPosition: 'left' },
                command: () => {
                    this.addTaxa('C');
                }
            },
            {
                icon: 'pi pi-plus-circle',
                label: 'Nova Taxa Extra',
                tooltipOptions: { tooltipLabel: 'Nova Taxa Extra', tooltipPosition: 'left' },
                disabled: false,
                command: () => {
                    this.addTaxa('E');
                }
            }
        ];

        this.speedDialItems = [
            {
                icon: 'pi pi-user',
                label: 'Nova Taxa Individual',
                tooltipOptions: { tooltipLabel: 'Nova Taxa Individual', tooltipPosition: 'left' },
                command: () => {
                    this.addTaxa('I');
                }
            },
            {
                icon: 'pi pi-tag',
                label: 'Novo Desconto',
                tooltipOptions: { tooltipLabel: 'Novo Desconto', tooltipPosition: 'left' },
                command: () => {
                    this.addTaxa('D');
                }
            },
            {
                icon: 'pi pi-refresh',
                label: 'Nova Renegociação',
                tooltipOptions: { tooltipLabel: 'Nova Renegociação', tooltipPosition: 'left' },
                disabled: true,
                command: () => {}
            }
        ];
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_condominio_config().then((res: any) => {
                if (res.status === 'success' && res.data && res.data.condominio && res.data.condominio.apartamentos) {
                    this.apartamentos = res.data.condominio.apartamentos;
                }
                this.loadTaxasComuns();
            });
        } else {
            this.apartamentos = ['101', '102', '103'];
            this.loadTaxasComuns();
        }
    }

    onTabChange(event: any) {
        this.activeTab = event;
        if (event === 'individuais') {
            this.loadTaxasIndividuais();
        } else if (event === 'comuns') {
            this.loadTaxasComuns();
        }
    }

    processTaxas(res: any) {
        if (res.status === 'success') {
            return res.data.map((t: any) => {
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
            return [];
        }
    }

    loadTaxasComuns() {
        this.loadingComuns = true;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_taxas(['C', 'E']).then((res: any) => {
                this.loadingComuns = false;
                this.taxasComuns = this.processTaxas(res);
                this.cdr.detectChanges();
            }).catch(() => {
                this.loadingComuns = false;
                this.cdr.detectChanges();
            });
        } else {
            this.loadingComuns = false;
            if (window.location.hostname === 'localhost') {
                this.taxasComuns = [
                    { id: 1, tipo: 'C', apartamento: null, competencia: '2026-07', exibicao: 'JUL/2026', vencimento: '14/07/2026', descricao: 'Taxa Ordinária', valor_original: 1500, desconto_vista: 0, multa_atraso: 0, juros_dia_atraso: 0 }
                ];
            }
        }
    }

    loadTaxasIndividuais() {
        this.loadingIndividuais = true;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_taxas(['I', 'D']).then((res: any) => {
                this.loadingIndividuais = false;
                this.taxasIndividuaisLoaded = true;
                this.taxasIndividuais = this.processTaxas(res);
                this.cdr.detectChanges();
            }).catch(() => {
                this.loadingIndividuais = false;
                this.taxasIndividuaisLoaded = true;
                this.cdr.detectChanges();
            });
        } else {
            this.loadingIndividuais = false;
            this.taxasIndividuaisLoaded = true;
            if (window.location.hostname === 'localhost') {
                this.taxasIndividuais = [];
            }
        }
    }

    addTaxa(tipo: string = 'C') {
        this.isEdit = false;
        this.dialogTitle = tipo === 'C' ? 'Nova Taxa Comum' : (tipo === 'E' ? 'Nova Taxa Extra' : (tipo === 'D' ? 'Novo Desconto' : 'Nova Taxa Individual'));
        this.currentTaxa = {
            tipo: tipo,
            apartamento: null,
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
        if (this.currentTaxa.tipo === 'D') this.loadTaxasParaDesconto();
    }

    loadTaxasParaDesconto() {
        if (this.currentTaxa.tipo !== 'D' || !this.currentTaxa.apartamento || !this.competenciaDate) {
            this.taxasParaDesconto = [];
            return;
        }
        const c = this.competenciaDate;
        const compStr = `${c.getFullYear()}-${String(c.getMonth() + 1).padStart(2, '0')}`;
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_taxas_por_apartamento(this.currentTaxa.apartamento, compStr, ['C', 'I', 'E']).then((res: any) => {
                if (res.status === 'success') {
                    this.taxasParaDesconto = res.data;
                }
            });
        }
    }

    onDescontoChange() {
        this.currentTaxa.taxa_id = null;
        this.taxasParaDesconto = [];
        this.loadTaxasParaDesconto();
    }

    getSelectedTaxa() {
        if (!this.currentTaxa.taxa_id || !this.taxasParaDesconto) return null;
        return this.taxasParaDesconto.find(t => t.id === this.currentTaxa.taxa_id);
    }

    editTaxa(taxa: any) {
        this.isEdit = true;
        this.dialogTitle = taxa.tipo === 'C' ? 'Editar Taxa Comum' : (taxa.tipo === 'E' ? 'Editar Taxa Extra' : (taxa.tipo === 'D' ? 'Editar Desconto' : 'Editar Taxa Individual'));
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
        if (this.currentTaxa.tipo === 'D') this.loadTaxasParaDesconto();
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
            if (!this.apartamentos.includes(this.currentTaxa.apartamento.trim())) {
                this.messageService.add({ severity: 'error', summary: 'Atenção', detail: `O apartamento ${this.currentTaxa.apartamento} não existe no condomínio.` });
                return;
            }
        }
        
        if (this.currentTaxa.tipo === 'D') {
            if (!this.currentTaxa.taxa_id) {
                this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Selecione a taxa referente ao desconto.' });
                return;
            }
            
            // Força valores positivos
            this.currentTaxa.valor_original = Math.abs(this.currentTaxa.valor_original || 0);
            this.currentTaxa.desconto_vista = Math.abs(this.currentTaxa.desconto_vista || 0);
            this.currentTaxa.multa_atraso = Math.abs(this.currentTaxa.multa_atraso || 0);
            this.currentTaxa.juros_dia_atraso = Math.abs(this.currentTaxa.juros_dia_atraso || 0);
            
            // Validar se valor é menor ou igual a taxa
            const taxaPai = this.taxasParaDesconto.find(t => t.id === this.currentTaxa.taxa_id);
            if (taxaPai) {
                if (this.currentTaxa.valor_original > taxaPai.valor_original || 
                    this.currentTaxa.desconto_vista > taxaPai.desconto_vista ||
                    this.currentTaxa.multa_atraso > taxaPai.multa_atraso ||
                    this.currentTaxa.juros_dia_atraso > taxaPai.juros_dia_atraso) {
                    this.messageService.add({ severity: 'error', summary: 'Atenção', detail: 'Os valores do desconto não podem ser maiores que os valores originais da taxa.' });
                    return;
                }
            }
        }
        
        this.currentTaxa.desconto_vista = this.currentTaxa.desconto_vista ?? 0;
        this.currentTaxa.multa_atraso = this.currentTaxa.multa_atraso ?? 0;
        this.currentTaxa.juros_dia_atraso = this.currentTaxa.juros_dia_atraso ?? 0;
        
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
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            let action = this.isEdit ? 
                pywebview.api.update_taxa(this.currentTaxa.id, payload) : 
                pywebview.api.insert_taxa(payload);
                
            action.then((res: any) => {
                if (res.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro salvo com sucesso.' });
                    this.displayDialog = false;
                    if (this.currentTaxa.tipo === 'I' || this.currentTaxa.tipo === 'D') this.loadTaxasIndividuais();
                    else this.loadTaxasComuns();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        } else {
            // Mock
            this.displayDialog = false;
            if (this.currentTaxa.tipo === 'I' || this.currentTaxa.tipo === 'D') this.loadTaxasIndividuais();
            else this.loadTaxasComuns();
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
                    pywebview.api.delete_taxa(this.currentTaxa.id).then((res: any) => {
                        if (res.status === 'success') {
                            this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Registro excluído com sucesso.' });
                            this.displayDialog = false;
                            if (this.currentTaxa.tipo === 'I' || this.currentTaxa.tipo === 'D') this.loadTaxasIndividuais();
                            else this.loadTaxasComuns();
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
