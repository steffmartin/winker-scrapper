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
import { MultiSelectModule } from 'primeng/multiselect';
import { SpeedDialModule } from 'primeng/speeddial';
import { TooltipModule } from 'primeng/tooltip';
import { FormsModule } from '@angular/forms';
import { MessageService, ConfirmationService, MenuItem } from 'primeng/api';

import { InputGroupModule } from 'primeng/inputgroup';
import { InputGroupAddonModule } from 'primeng/inputgroupaddon';

@Component({
    selector: 'app-cobrancas',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        InputTextModule, InputNumberModule, DatePickerModule, InputMaskModule,
        DialogModule, ConfirmDialogModule, ToastModule, AvatarModule, SpeedDialModule, SelectModule, MultiSelectModule, TooltipModule, FormsModule, InputGroupModule, InputGroupAddonModule
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
    
    displayDialogRenegociacao: boolean = false;
    todayDate: Date = new Date();
    currentRenegociacao: any = {};
    taxasOriginaisParaRenegociacao: any[] = [];
    taxasOriginaisSelecionadas: any[] = [];
    parcelasGeradas: any[] = [];
    dataRenegociacaoDate: Date | null = null;
    competenciaRenegociacaoRange: Date[] = [];
    vencimentoPrimeiraParcelaDate: Date | null = null;
    quantidadeParcelas: number = 1;
    despesasAdicionais: number = 0;
    descontosAdicionais: number = 0;
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
                disabled: false,
                command: () => {
                    this.addRenegociacao();
                }
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

    getTipoAvatarColor(tipo: string): string {
        switch(tipo) {
            case 'C': return '#3b82f6'; // blue
            case 'E': return '#8b5cf6'; // purple
            case 'I': return '#10b981'; // emerald
            case 'D': return '#ef4444'; // red
            case 'P': return '#f59e0b'; // amber
            case 'R': return '#ec4899'; // pink
            default: return '#64748b'; // slate
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
            pywebview.api.get_taxas(['I', 'D', 'P']).then((res: any) => {
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
            pywebview.api.get_taxas_por_apartamento(this.currentTaxa.apartamento, [compStr, compStr], ['C', 'I', 'E', 'P']).then((res: any) => {
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
        if (taxa.tipo === 'P' || taxa.tipo === 'R') {
            this.editRenegociacao(taxa.renegociacao_id);
            return;
        }
        
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

    addRenegociacao() {
        this.isEdit = false;
        this.currentRenegociacao = {
            apartamento: null,
            numero: ''
        };
        this.dataRenegociacaoDate = new Date();
        this.competenciaRenegociacaoRange = [];
        this.taxasOriginaisParaRenegociacao = [];
        this.taxasOriginaisSelecionadas = [];
        this.parcelasGeradas = [];
        this.todayDate = new Date();
        this.vencimentoPrimeiraParcelaDate = new Date();
        this.quantidadeParcelas = 1;
        this.despesasAdicionais = 0;
        this.descontosAdicionais = 0;
        this.displayDialogRenegociacao = true;
    }

    onRenegociacaoFormChange() {
        this.parcelasGeradas = []; 
        this.taxasOriginaisParaRenegociacao = [];
        this.taxasOriginaisSelecionadas = [];
        
        if (!this.dataRenegociacaoDate || !this.currentRenegociacao.apartamento || !this.competenciaRenegociacaoRange || this.competenciaRenegociacaoRange.length < 2) {
            return;
        }

        const isValidApto = this.apartamentos.includes(this.currentRenegociacao.apartamento);
        if (!isValidApto) return;
        
        const c1 = this.competenciaRenegociacaoRange[0];
        const c2 = this.competenciaRenegociacaoRange[1];
        if (!c1 || !c2) return;
        
        const compStr1 = `${c1.getFullYear()}-${String(c1.getMonth() + 1).padStart(2, '0')}`;
        const compStr2 = `${c2.getFullYear()}-${String(c2.getMonth() + 1).padStart(2, '0')}`;
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_taxas_por_apartamento(this.currentRenegociacao.apartamento, [compStr1, compStr2], ['C', 'E', 'I']).then((res: any) => {
                if (res.status === 'success') {
                    this.taxasOriginaisParaRenegociacao = res.data.map((t: any) => {
                        t.displayLabel = `${t.exibicao} - ${t.descricao} (R$ ${t.valor_original})`;
                        return t;
                    });
                    this.cdr.detectChanges();
                }
            });
        }
    }

    onTaxasOriginaisChange() {
        this.parcelasGeradas = [];
    }
    
    getDiasAtraso(vencimentoStr: string): number {
        if (!vencimentoStr || !this.dataRenegociacaoDate) return 0;
        const parts = vencimentoStr.split('/');
        if (parts.length !== 3) return 0;
        
        // Ignora a hora para garantir cálculo preciso de dias
        const vencDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
        vencDate.setHours(0, 0, 0, 0);
        
        const renDate = new Date(this.dataRenegociacaoDate);
        renDate.setHours(0, 0, 0, 0);
        
        const diffTime = renDate.getTime() - vencDate.getTime();
        const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
        return diffDays > 0 ? diffDays : 0;
    }

    get selectedTaxasSum(): number {
        if (!this.taxasOriginaisSelecionadas || this.taxasOriginaisSelecionadas.length === 0) return 0;
        return this.taxasOriginaisSelecionadas.reduce((sum, t) => {
            const dias = this.getDiasAtraso(t.vencimento);
            const jurosTotal = (t.juros_dia_atraso || 0) * dias;
            return sum + (t.valor_original || 0) + (t.multa_atraso || 0) + jurosTotal;
        }, 0);
    }
    
    get selectedTaxasDetalhesSum() {
        if (!this.taxasOriginaisSelecionadas || this.taxasOriginaisSelecionadas.length === 0) {
            return { valor: 0, desconto: 0, multa: 0, juros: 0 };
        }
        return this.taxasOriginaisSelecionadas.reduce((acc, t) => {
            const dias = this.getDiasAtraso(t.vencimento);
            const jurosTotal = (t.juros_dia_atraso || 0) * dias;
            
            acc.valor += (t.valor_original || 0);
            acc.desconto += 0; 
            acc.multa += (t.multa_atraso || 0);
            acc.juros += jurosTotal;
            return acc;
        }, { valor: 0, desconto: 0, multa: 0, juros: 0 });
    }
    
    gerarParcelasRenegociacao() {
        if (!this.vencimentoPrimeiraParcelaDate || this.quantidadeParcelas < 1) return;
        if (!this.taxasOriginaisSelecionadas || this.taxasOriginaisSelecionadas.length === 0) return;
        
        const baseVal = this.selectedTaxasSum;
        const total = baseVal + (this.despesasAdicionais || 0) - (this.descontosAdicionais || 0);
        
        if (total <= 0) return;
        
        const parcelaBase = Math.floor((total / this.quantidadeParcelas) * 100) / 100;
        const primeiraParcela = Math.round((total - (parcelaBase * (this.quantidadeParcelas - 1))) * 100) / 100;
        
        this.parcelasGeradas = [];
        
        for (let i = 0; i < this.quantidadeParcelas; i++) {
            const vDate = new Date(this.vencimentoPrimeiraParcelaDate);
            vDate.setMonth(vDate.getMonth() + i);
            const vencStr = `${String(vDate.getDate()).padStart(2, '0')}/${String(vDate.getMonth() + 1).padStart(2, '0')}/${vDate.getFullYear()}`;
            
            const num = i + 1;
            const baseDesc = `Renegociação ${this.currentRenegociacao.numero || ''}`.trim();
            const desc = `${baseDesc} ${num}/${this.quantidadeParcelas}`;
            const valor = i === 0 ? primeiraParcela : parcelaBase;
            
            const compDate = new Date(vDate.getFullYear(), vDate.getMonth(), 1);

            this.parcelasGeradas.push({
                numero: num,
                vencimento: vDate,
                descricao: desc,
                competencia: compDate,
                valor_original: valor,
                desconto_vista: 0,
                valor_a_vista: valor,
                multa_atraso: 0,
                juros_dia_atraso: 0
            });
        }
    }
    
    updateValorAVista(p: any) {
        p.valor_a_vista = (p.valor_original || 0) - (p.desconto_vista || 0);
    }
    
    get parcelasSum(): number {
        if (!this.parcelasGeradas || this.parcelasGeradas.length === 0) return 0;
        return this.parcelasGeradas.reduce((sum, p) => sum + (p.valor_original || 0), 0);
    }
    
    get parcelasDescontoSum(): number {
        if (!this.parcelasGeradas || this.parcelasGeradas.length === 0) return 0;
        return this.parcelasGeradas.reduce((sum, p) => sum + (p.desconto_vista || 0), 0);
    }
    
    get isRenegociacaoValid(): boolean {
        const expected = Math.round((this.selectedTaxasSum + (this.despesasAdicionais || 0) - (this.descontosAdicionais || 0)) * 100) / 100;
        const actual = Math.round(this.parcelasSum * 100) / 100;
        
        return this.parcelasGeradas.length > 0 && 
               expected === actual && 
               this.currentRenegociacao.apartamento && 
               this.dataRenegociacaoDate !== null && 
               this.competenciaRenegociacaoRange && 
               this.competenciaRenegociacaoRange.length === 2;
    }
    
    saveRenegociacao() {
        if (!this.isRenegociacaoValid) return;
        
        const c1 = this.competenciaRenegociacaoRange[0];
        const c2 = this.competenciaRenegociacaoRange[1];
        const compStr1 = `${c1.getFullYear()}-${String(c1.getMonth() + 1).padStart(2, '0')}`;
        const compStr2 = `${c2.getFullYear()}-${String(c2.getMonth() + 1).padStart(2, '0')}`;
        
        const dataR = this.dataRenegociacaoDate!;
        const dataRStr = `${String(dataR.getDate()).padStart(2, '0')}/${String(dataR.getMonth() + 1).padStart(2, '0')}/${dataR.getFullYear()}`;
        
        const venc1 = this.vencimentoPrimeiraParcelaDate;
        const venc1Str = venc1 ? `${String(venc1.getDate()).padStart(2, '0')}/${String(venc1.getMonth() + 1).padStart(2, '0')}/${venc1.getFullYear()}` : null;

        const payload = {
            id: this.currentRenegociacao.id,
            apartamento: this.currentRenegociacao.apartamento,
            numero: this.currentRenegociacao.numero,
            competencia_inicial: compStr1,
            competencia_final: compStr2,
            data_renegociacao: dataRStr,
            vencimento_primeira_parcela: venc1Str,
            quantidade_parcelas: this.quantidadeParcelas,
            despesas_adicionais: this.despesasAdicionais,
            descontos_adicionais: this.descontosAdicionais,
            taxas_originais: this.taxasOriginaisSelecionadas.map(t => t.id || t.taxa_id),
            parcelas: this.parcelasGeradas.map(p => {
                const v = p.vencimento;
                const c = p.competencia;
                return {
                    ...p,
                    vencimento: v instanceof Date ? `${String(v.getDate()).padStart(2, '0')}/${String(v.getMonth() + 1).padStart(2, '0')}/${v.getFullYear()}` : p.vencimento,
                    competencia: c instanceof Date ? `${c.getFullYear()}-${String(c.getMonth() + 1).padStart(2, '0')}` : p.competencia
                };
            })
        };
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.salvar_renegociacao(payload).then((res: any) => {
                if (res.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Renegociação salva com sucesso.' });
                    this.displayDialogRenegociacao = false;
                    this.loadTaxasIndividuais();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        }
    }
    
    editRenegociacao(id: number) {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_renegociacao(id).then((res: any) => {
                if (res.status === 'success') {
                    this.isEdit = true;
                    const d = res.data;
                    this.currentRenegociacao = {
                        id: d.id,
                        apartamento: d.apartamento,
                        numero: d.numero
                    };
                    
                    const partsD = d.data_renegociacao.split('/');
                    this.dataRenegociacaoDate = new Date(parseInt(partsD[2]), parseInt(partsD[1]) - 1, parseInt(partsD[0]));
                    
                    if (d.vencimento_primeira_parcela) {
                        const partsV = d.vencimento_primeira_parcela.split('/');
                        this.vencimentoPrimeiraParcelaDate = new Date(parseInt(partsV[2]), parseInt(partsV[1]) - 1, parseInt(partsV[0]));
                    } else {
                        this.vencimentoPrimeiraParcelaDate = null;
                    }
                    
                    this.quantidadeParcelas = d.quantidade_parcelas || 1;
                    this.despesasAdicionais = d.despesas_adicionais || 0.0;
                    this.descontosAdicionais = d.descontos_adicionais || 0.0;
                    
                    const c1p = d.competencia_inicial.split('-');
                    const c2p = d.competencia_final.split('-');
                    this.competenciaRenegociacaoRange = [
                        new Date(parseInt(c1p[0]), parseInt(c1p[1]) - 1, 1),
                        new Date(parseInt(c2p[0]), parseInt(c2p[1]) - 1, 1)
                    ];
                    
                    // Note: we can't fully reconstruct the multi-select without fetching all original taxes of the apt again
                    // so we simulate it by loading the original taxes
                    const c1 = this.competenciaRenegociacaoRange[0];
                    const c2 = this.competenciaRenegociacaoRange[1];
                    const compStr1 = `${c1.getFullYear()}-${String(c1.getMonth() + 1).padStart(2, '0')}`;
                    const compStr2 = `${c2.getFullYear()}-${String(c2.getMonth() + 1).padStart(2, '0')}`;
                    
                    pywebview.api.get_taxas_por_apartamento(this.currentRenegociacao.apartamento, [compStr1, compStr2], ['C', 'E', 'I']).then((resTaxas: any) => {
                        if (resTaxas.status === 'success') {
                            this.taxasOriginaisParaRenegociacao = resTaxas.data.map((t: any) => {
                                t.displayLabel = `${t.exibicao} - ${t.descricao} (R$ ${t.valor_original})`;
                                return t;
                            });
                            
                            const origIds = d.taxas_originais.map((t:any) => t.taxa_id);
                            this.taxasOriginaisSelecionadas = this.taxasOriginaisParaRenegociacao.filter(t => origIds.includes(t.id));
                            
                            this.parcelasGeradas = d.parcelas.map((p:any) => {
                                let vDate = null;
                                if (p.vencimento) {
                                    const parts = p.vencimento.split('/');
                                    vDate = new Date(parseInt(parts[2]), parseInt(parts[1])-1, parseInt(parts[0]));
                                }
                                let cDate = null;
                                if (p.competencia) {
                                    const parts = p.competencia.split('-');
                                    cDate = new Date(parseInt(parts[0]), parseInt(parts[1])-1, 1);
                                }
                                return {
                                    ...p,
                                    numero: p.descricao.split(' ').pop(),
                                    vencimento: vDate,
                                    competencia: cDate,
                                    valor_a_vista: (p.valor_original || 0) - (p.desconto_vista || 0)
                                };
                            });
                            
                            this.displayDialogRenegociacao = true;
                            this.cdr.detectChanges();
                        }
                    });
                }
            });
        }
    }
    
    deleteRenegociacao() {
        if (!this.currentRenegociacao.id) return;
        this.confirmationService.confirm({
            message: 'Tem certeza que deseja excluir esta renegociação e todas suas parcelas?',
            header: 'Confirmação',
            icon: 'pi pi-exclamation-triangle',
            acceptLabel: 'Sim',
            rejectLabel: 'Não',
            acceptButtonStyleClass: 'p-button-danger',
            rejectButtonStyleClass: 'p-button-secondary p-button-text',
            accept: () => {
                const pywebview = (window as any).pywebview;
                if (pywebview && pywebview.api) {
                    pywebview.api.delete_renegociacao(this.currentRenegociacao.id).then((res: any) => {
                        if (res.status === 'success') {
                            this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Renegociação excluída.' });
                            this.displayDialogRenegociacao = false;
                            this.loadTaxasIndividuais();
                        } else {
                            this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                        }
                    });
                }
            }
        });
    }
}
