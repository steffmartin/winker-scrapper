import { Component, OnInit, Input, Output, EventEmitter, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { MultiSelectModule } from 'primeng/multiselect';
import { TooltipModule } from 'primeng/tooltip';
import { TableModule } from 'primeng/table';
import { InputGroupModule } from 'primeng/inputgroup';
import { FormsModule } from '@angular/forms';
import { MessageService, ConfirmationService } from 'primeng/api';

declare global {
    interface Window {
        pywebview?: any;
    }
}

@Component({
    selector: 'app-renegociacao-dialog',
    standalone: true,
    imports: [
        CommonModule, ButtonModule, InputTextModule, InputNumberModule,
        DatePickerModule, DialogModule, MultiSelectModule, TooltipModule,
        TableModule, InputGroupModule, FormsModule
    ],
    templateUrl: './renegociacao-dialog.html',
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
    `]
})
export class RenegociacaoDialogComponent implements OnInit, OnChanges {
    @Input() visible: boolean = false;
    @Output() visibleChange = new EventEmitter<boolean>();
    
    @Input() renegociacaoId?: number;
    @Input() autoFillApartamento?: string;
    @Input() autoFillCompetenciaRange?: Date[];
    @Input() autoFillTaxasOriginaisIds?: number[];
    
    @Output() onSave = new EventEmitter<void>();
    @Output() onDelete = new EventEmitter<void>();

    isEdit: boolean = false;
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
    
    apartamentos: string[] = [];
    tipo_juros_multa: string = 'N';
    taxa_renegociacao_config: number = 0;

    constructor(
        private cdr: ChangeDetectorRef,
        private messageService: MessageService,
        private confirmationService: ConfirmationService
    ) {}

    ngOnInit() {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_condominio_config().then((res: any) => {
                if (res.status === 'success' && res.data && res.data.condominio) {
                    if (res.data.condominio.apartamentos) {
                        this.apartamentos = res.data.condominio.apartamentos;
                    }
                    this.tipo_juros_multa = res.data.condominio.tipo_juros_multa || 'N';
                    this.taxa_renegociacao_config = res.data.condominio.taxa_renegociacao || 0;
                }
            });
        }
    }

    ngOnChanges(changes: SimpleChanges) {
        if (changes['visible'] && changes['visible'].currentValue) {
            if (this.renegociacaoId) {
                this.editRenegociacao(this.renegociacaoId);
            } else {
                this.initNovaRenegociacao();
            }
        }
    }

    initNovaRenegociacao() {
        this.isEdit = false;
        this.currentRenegociacao = {
            apartamento: this.autoFillApartamento || null,
            numero: ''
        };
        this.dataRenegociacaoDate = new Date();
        this.competenciaRenegociacaoRange = this.autoFillCompetenciaRange || [];
        this.taxasOriginaisParaRenegociacao = [];
        this.taxasOriginaisSelecionadas = [];
        this.parcelasGeradas = [];
        this.todayDate = new Date();
        this.vencimentoPrimeiraParcelaDate = new Date();
        this.quantidadeParcelas = 1;
        this.despesasAdicionais = 0;
        this.descontosAdicionais = 0;
        
        if (this.autoFillApartamento && this.autoFillCompetenciaRange && this.autoFillCompetenciaRange.length === 2) {
            this.onRenegociacaoFormChange(true);
        }
    }

    closeDialog() {
        this.visible = false;
        this.visibleChange.emit(false);
    }

    onRenegociacaoFormChange(isAutoFill: boolean = false) {
        if (!isAutoFill) {
            this.parcelasGeradas = []; 
            this.taxasOriginaisParaRenegociacao = [];
            this.taxasOriginaisSelecionadas = [];
        }
        
        if (!this.dataRenegociacaoDate || !this.currentRenegociacao.apartamento || !this.competenciaRenegociacaoRange || this.competenciaRenegociacaoRange.length < 2) {
            return;
        }

        const isValidApto = this.apartamentos.includes(this.currentRenegociacao.apartamento) || this.apartamentos.length === 0;
        if (!isValidApto) return;
        
        const c1 = this.competenciaRenegociacaoRange[0];
        const c2 = this.competenciaRenegociacaoRange[1];
        if (!c1 || !c2) return;
        
        const compStr1 = `${c1.getFullYear()}-${String(c1.getMonth() + 1).padStart(2, '0')}`;
        const compStr2 = `${c2.getFullYear()}-${String(c2.getMonth() + 1).padStart(2, '0')}`;
        
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_taxas_por_apartamento(this.currentRenegociacao.apartamento, [compStr1, compStr2], ['C', 'E', 'I']).then((res: any) => {
                if (res.status === 'success') {
                    this.taxasOriginaisParaRenegociacao = res.data.map((t: any) => {
                        t.displayLabel = `${t.exibicao} - ${t.descricao} (R$ ${t.valor_original})`;
                        return t;
                    });
                    
                    if (isAutoFill && this.autoFillTaxasOriginaisIds && this.autoFillTaxasOriginaisIds.length > 0) {
                        this.taxasOriginaisSelecionadas = this.taxasOriginaisParaRenegociacao.filter(t => this.autoFillTaxasOriginaisIds!.includes(t.id));
                        this.onTaxasOriginaisChange();
                    }
                    
                    this.cdr.detectChanges();
                }
            });
        }
    }

    onTaxasOriginaisChange() {
        this.parcelasGeradas = [];
        const total = this.selectedTaxasSum;
        this.despesasAdicionais = total * (this.taxa_renegociacao_config / 100.0);
    }
    
    getDiasAtraso(vencimentoStr: string): number {
        if (!vencimentoStr || !this.dataRenegociacaoDate) return 0;
        const parts = vencimentoStr.split('/');
        if (parts.length !== 3) return 0;
        
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
            let jurosTotal = 0;
            let multaTotal = 0;
            const jurosPerc = t.juros_mes_percentual || 0;
            const multaPerc = t.multa_percentual || 0;
            const totalSemDesconto = t.valor_original || 0;

            if (this.tipo_juros_multa === 'M') {
                jurosTotal = totalSemDesconto * (jurosPerc / 30.0 / 100.0) * dias;
                multaTotal = (totalSemDesconto + jurosTotal) * (multaPerc / 100.0);
            } else if (this.tipo_juros_multa === 'J') {
                multaTotal = totalSemDesconto * (multaPerc / 100.0);
                jurosTotal = (totalSemDesconto + multaTotal) * (jurosPerc / 30.0 / 100.0) * dias;
            } else {
                jurosTotal = totalSemDesconto * (jurosPerc / 30.0 / 100.0) * dias;
                multaTotal = totalSemDesconto * (multaPerc / 100.0);
            }

            return sum + totalSemDesconto + multaTotal + jurosTotal;
        }, 0);
    }
    
    get selectedTaxasDetalhesSum() {
        if (!this.taxasOriginaisSelecionadas || this.taxasOriginaisSelecionadas.length === 0) {
            return { valor: 0, desconto: 0, multa: 0, juros: 0, geral: 0 };
        }
        return this.taxasOriginaisSelecionadas.reduce((acc, t) => {
            const dias = this.getDiasAtraso(t.vencimento);
            let jurosTotal = 0;
            let multaTotal = 0;
            const jurosPerc = t.juros_mes_percentual || 0;
            const multaPerc = t.multa_percentual || 0;
            const totalSemDesconto = t.valor_original || 0;

            if (this.tipo_juros_multa === 'M') {
                jurosTotal = totalSemDesconto * (jurosPerc / 30.0 / 100.0) * dias;
                multaTotal = (totalSemDesconto + jurosTotal) * (multaPerc / 100.0);
            } else if (this.tipo_juros_multa === 'J') {
                multaTotal = totalSemDesconto * (multaPerc / 100.0);
                jurosTotal = (totalSemDesconto + multaTotal) * (jurosPerc / 30.0 / 100.0) * dias;
            } else {
                jurosTotal = totalSemDesconto * (jurosPerc / 30.0 / 100.0) * dias;
                multaTotal = totalSemDesconto * (multaPerc / 100.0);
            }
            
            acc.valor += totalSemDesconto;
            acc.desconto += 0; 
            acc.multa += multaTotal;
            acc.juros += jurosTotal;
            acc.geral += totalSemDesconto + multaTotal + jurosTotal;
            return acc;
        }, { valor: 0, desconto: 0, multa: 0, juros: 0, geral: 0 });
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
                multa_percentual: 0,
                juros_mes_percentual: 0
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
        
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.salvar_renegociacao(payload).then((res: any) => {
                if (res.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Renegociação salva com sucesso.' });
                    this.onSave.emit();
                    this.closeDialog();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        }
    }
    
    editRenegociacao(id: number) {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_renegociacao(id).then((res: any) => {
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
                    
                    const c1 = this.competenciaRenegociacaoRange[0];
                    const c2 = this.competenciaRenegociacaoRange[1];
                    const compStr1 = `${c1.getFullYear()}-${String(c1.getMonth() + 1).padStart(2, '0')}`;
                    const compStr2 = `${c2.getFullYear()}-${String(c2.getMonth() + 1).padStart(2, '0')}`;
                    
                    window.pywebview.api.get_taxas_por_apartamento(this.currentRenegociacao.apartamento, [compStr1, compStr2], ['C', 'E', 'I']).then((resTaxas: any) => {
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
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.delete_renegociacao(this.currentRenegociacao.id).then((res: any) => {
                        if (res.status === 'success') {
                            this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: 'Renegociação excluída.' });
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
