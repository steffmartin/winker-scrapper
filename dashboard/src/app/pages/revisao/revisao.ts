import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { TabsModule } from 'primeng/tabs';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { BadgeModule } from 'primeng/badge';
import { ChipModule } from 'primeng/chip';
import { AvatarModule } from 'primeng/avatar';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { MessageService, ConfirmationService } from 'primeng/api';
import { DialogService, DynamicDialogRef } from 'primeng/dynamicdialog';
import { DialogEdicaoComponent } from './dialog-edicao';
import { LayoutService } from '@/app/layout/service/layout.service';

@Component({
    selector: 'app-revisao',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        BadgeModule, ChipModule, AvatarModule, ToastModule, ConfirmDialogModule
    ],
    providers: [MessageService, ConfirmationService, DialogService],
    templateUrl: './revisao.html',
    styles: [`
        :host ::ng-deep .p-tabs-list {
            margin-bottom: 1rem;
        }
        :host ::ng-deep .p-tabpanels {
            padding: 0 !important;
        }
        :host ::ng-deep .p-paginator {
            padding-top: 1rem !important;
        }
    `]
})
export class RevisaoComponent implements OnInit {
    loadingCounts: boolean = true;
    activeTab: string = '3'; // meses first
    pendenciasCounts: any = {
        lancamentos: 0,
        subcategorias: 0,
        categorias: 0,
        meses: 0,
        documentos: 0
    };

    lancamentos: any[] = [];
    subcategorias: any[] = [];
    categorias: any[] = [];
    meses: any[] = [];
    documentos: any[] = [];

    loadingLancamentos = false;
    loadingSubcategorias = false;
    loadingCategorias = false;
    loadingMeses = false;
    loadingDocumentos = false;

    ref: DynamicDialogRef | undefined | null;

    constructor(
        private cdr: ChangeDetectorRef,
        private messageService: MessageService,
        private dialogService: DialogService,
        private layoutService: LayoutService
    ) {}

    ngOnInit() {
        this.loadCounts();
    }

    loadCounts() {
        this.loadingCounts = true;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_pendencias_revisao_count().then((res: any) => {
                this.loadingCounts = false;
                if (res.status === 'success' && res.data && res.data.details) {
                    this.pendenciasCounts = {
                        lancamentos: res.data.details.lancamentos || 0,
                        subcategorias: res.data.details.subcategorias || 0,
                        categorias: res.data.details.categorias || 0,
                        meses: res.data.details.meses || 0,
                        documentos: res.data.details.documentos || 0
                    };
                } else {
                    this.pendenciasCounts = { lancamentos: 0, subcategorias: 0, categorias: 0, meses: 0, documentos: 0 };
                }
                this.cdr.detectChanges();
                this.cdr.detectChanges();
                this.setDefaultTab();
            }).catch(() => {
                this.loadingCounts = false;
                this.cdr.detectChanges();
            });
        } else {
            this.loadingCounts = false;
            // mock
            if (window.location.hostname === 'localhost') {
                if (typeof (window as any).__mockHasInconsistencies === 'undefined') {
                    (window as any).__mockHasInconsistencies = Math.random() > 0.5;
                }
                if ((window as any).__mockHasInconsistencies) {
                    this.pendenciasCounts = { lancamentos: 5, subcategorias: 1, categorias: 2, meses: 1, documentos: 3 };
                } else {
                    this.pendenciasCounts = { lancamentos: 0, subcategorias: 0, categorias: 0, meses: 0, documentos: 0 };
                }
                this.setDefaultTab();
            }
        }
    }

    hasPendencias(): boolean {
        return this.pendenciasCounts.meses > 0 || 
               this.pendenciasCounts.categorias > 0 || 
               this.pendenciasCounts.subcategorias > 0 || 
               this.pendenciasCounts.lancamentos > 0 || 
               this.pendenciasCounts.documentos > 0;
    }

    setDefaultTab() {
        if (!this.hasPendencias()) {
            this.activeTab = '-1';
            return;
        }

        const tabMap: any = {
            '0': 'lancamentos',
            '1': 'subcategorias',
            '2': 'categorias',
            '3': 'meses',
            '4': 'documentos'
        };

        if (this.activeTab && this.activeTab !== '-1' && this.pendenciasCounts[tabMap[this.activeTab]] > 0) {
            // mantém a aba
        } else {
            if (this.pendenciasCounts.meses > 0) this.activeTab = '3';
            else if (this.pendenciasCounts.categorias > 0) this.activeTab = '2';
            else if (this.pendenciasCounts.subcategorias > 0) this.activeTab = '1';
            else if (this.pendenciasCounts.lancamentos > 0) this.activeTab = '0';
            else if (this.pendenciasCounts.documentos > 0) this.activeTab = '4';
        }
        
        if (this.activeTab !== '-1') {
            this.loadActiveTabContent(this.activeTab);
        }
    }

    onTabChange(event: any) {
        this.activeTab = event;
        this.loadActiveTabContent(event);
    }

    loadActiveTabContent(tabValue: string) {
        if (tabValue === '0' && this.pendenciasCounts.lancamentos > 0 && this.lancamentos.length === 0) {
            this.loadTableData('lancamentos');
        } else if (tabValue === '1' && this.pendenciasCounts.subcategorias > 0 && this.subcategorias.length === 0) {
            this.loadTableData('subcategorias');
        } else if (tabValue === '2' && this.pendenciasCounts.categorias > 0 && this.categorias.length === 0) {
            this.loadTableData('categorias');
        } else if (tabValue === '3' && this.pendenciasCounts.meses > 0 && this.meses.length === 0) {
            this.loadTableData('meses');
        } else if (tabValue === '4' && this.pendenciasCounts.documentos > 0 && this.documentos.length === 0) {
            this.loadTableData('documentos');
        }
    }

    loadTableData(tipo_tabela: string) {
        let loadingVar = 'loading' + tipo_tabela.charAt(0).toUpperCase() + tipo_tabela.slice(1);
        (this as any)[loadingVar] = true;
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_registros_nao_revisados(tipo_tabela).then((res: any) => {
                (this as any)[loadingVar] = false;
                if (res.status === 'success') {
                    const dataWithCount = res.data.map((row: any) => {
                        row.inconsistencias_count = this.getInconsistenciasList(row.motivo_inconsistencia).length;
                        return row;
                    });
                    (this as any)[tipo_tabela] = dataWithCount;
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
                this.cdr.detectChanges();
            }).catch(() => {
                (this as any)[loadingVar] = false;
                this.cdr.detectChanges();
            });
        } else {
            (this as any)[loadingVar] = false;
            // mock
            if (window.location.hostname === 'localhost') {
                if (!(window as any).__mockHasInconsistencies) {
                    (this as any)[tipo_tabela] = [];
                } else {
                    if (tipo_tabela === 'lancamentos') {
                        this.lancamentos = [
                            { id: 1, mes_exibicao: 'JAN/2026', mes_competencia: '2026-01', data: '15/01/2026', descricao: 'Taxa Condominial', valor: 500, tipo: 'R', motivo_inconsistencia: '["Apartamento não identificado", "Competência não identificada", "Conta não identificada", "Quantidade de anexos divergente"]' },
                            { id: 2, mes_exibicao: 'JAN/2026', mes_competencia: '2026-01', data: '20/01/2026', descricao: 'Conserto Bomba', valor: 1200, tipo: 'D', motivo_inconsistencia: '["Fornecedor não identificado", "Despesa sem comprovantes", "Conta não identificada", "Quantidade de anexos divergente"]' }
                        ];
                    } else if (tipo_tabela === 'meses') {
                        this.meses = [
                            { id: 1, exibicao: 'JAN/2026', competencia: '2026-01', receita_total: 5000, despesa_total: 4000, motivo_inconsistencia: '["Divergência em receitas", "Divergência em despesas", "Mês sem prestação de contas"]' }
                        ];
                    } else if (tipo_tabela === 'documentos') {
                        this.documentos = [
                            { id: 1, mes_exibicao: 'JAN/2026', nome_original: 'arquivo_sem_extensao', tipo_doc: 'C', motivo_inconsistencia: '["Extensão de arquivo inválida ou ausente"]' }
                        ];
                    } else if (tipo_tabela === 'categorias') {
                        this.categorias = [
                            { id: 1, mes_exibicao: 'JAN/2026', nome: 'Manutenção', valor: 2500, motivo_inconsistencia: '["Soma das subcategorias difere do total da categoria"]' }
                        ];
                    } else if (tipo_tabela === 'subcategorias') {
                        this.subcategorias = [
                            { id: 1, mes_exibicao: 'JAN/2026', nome: 'Elevador', valor: 1000, motivo_inconsistencia: '["Soma das transações difere do total da subcategoria"]' }
                        ];
                    }
                }
            }
        }
    }

    editRow(rowData: any, tipo_tabela: string) {
        this.ref = this.dialogService.open(DialogEdicaoComponent, {
            header: 'Revisão de Registro',
            width: '40vw',
            modal: true,
            closable: true,
            closeOnEscape: true,
            dismissableMask: true,
            breakpoints: {
                '960px': '75vw',
                '640px': '90vw'
            },
            data: {
                registro: JSON.parse(JSON.stringify(rowData)),
                tipo_tabela: tipo_tabela
            }
        });

        if (this.ref) {
            this.ref.onClose.subscribe((result: any) => {
                if (result && result.status === 'success') {
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: result.message });
                    this.loadCounts();
                    this.loadTableData(tipo_tabela);
                    this.layoutService.onReviewSaved.next();
                }
            });
        }
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

    getInconsistenciasList(motivo: string): string[] {
        if (!motivo) return [];
        try {
            return JSON.parse(motivo);
        } catch (e) {
            // fallback se for texto puro
            return motivo.split('|').map(m => m.trim()).filter(m => m.length > 0);
        }
    }
}
