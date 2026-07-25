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
import { TaxaDialogComponent } from '../../shared/components/taxa-dialog/taxa-dialog.component';
import { RenegociacaoDialogComponent } from '../../shared/components/renegociacao-dialog/renegociacao-dialog.component';

@Component({
    selector: 'app-cobrancas',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        InputTextModule, InputNumberModule, DatePickerModule, InputMaskModule,
        DialogModule, ConfirmDialogModule, ToastModule, AvatarModule, SpeedDialModule, SelectModule, MultiSelectModule, TooltipModule, FormsModule, InputGroupModule, InputGroupAddonModule, TaxaDialogComponent, RenegociacaoDialogComponent
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
    tipo_juros_multa: string = 'N';
    taxa_renegociacao_config: number = 0;
    speedDialItems: MenuItem[] = [];
    speedDialComunsItems: MenuItem[] = [];
    
    displayDialog: boolean = false;
    isEdit: boolean = false;
    dialogTitle: string = '';
    currentTaxa: any = {};
    
    currentTaxaTipo: string = 'C';
    currentTaxaData: any = null;
    currentRenegociacaoId?: number;
    displayDialogRenegociacao: boolean = false;
    
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
                if (res.status === 'success' && res.data && res.data.condominio) {
                    if (res.data.condominio.apartamentos) {
                        this.apartamentos = res.data.condominio.apartamentos;
                    }
                    this.tipo_juros_multa = res.data.condominio.tipo_juros_multa || 'N';
                    this.taxa_renegociacao_config = res.data.condominio.taxa_renegociacao || 0;
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
                    { id: 1, tipo: 'C', apartamento: null, competencia: '2026-07', exibicao: 'JUL/2026', vencimento: '14/07/2026', descricao: 'Taxa Ordinária', valor_original: 1500, desconto_vista: 0, multa_percentual: 0, juros_mes_percentual: 0 }
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
        this.currentTaxaTipo = tipo;
        this.currentTaxaData = null;
        this.displayDialog = true;
    }

    editTaxa(taxa: any) {
        if (taxa.tipo === 'P' || taxa.tipo === 'R') {
            this.currentRenegociacaoId = taxa.renegociacao_id;
            this.displayDialogRenegociacao = true;
            return;
        }
        this.currentTaxaData = taxa;
        this.displayDialog = true;
    }

    addRenegociacao() {
        this.currentRenegociacaoId = undefined;
        this.displayDialogRenegociacao = true;
    }

    onDialogSave() {
        if (this.activeTab === 'individuais') {
            this.loadTaxasIndividuais();
        } else {
            this.loadTaxasComuns();
        }
    }

}
