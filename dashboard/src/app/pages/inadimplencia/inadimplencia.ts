import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { TabsModule } from 'primeng/tabs';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { DatePickerModule } from 'primeng/datepicker';
import { AvatarModule } from 'primeng/avatar';
import { FormsModule } from '@angular/forms';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { BadgeModule } from 'primeng/badge';
import { TooltipModule } from 'primeng/tooltip';
import { SkeletonModule } from 'primeng/skeleton';

declare global {
    interface Window {
        pywebview?: any;
    }
}

@Component({
    selector: 'app-inadimplencia',
    standalone: true,
    imports: [
        CommonModule, CardModule, TabsModule, TableModule, ButtonModule,
        InputTextModule, InputNumberModule, DatePickerModule, AvatarModule, 
        FormsModule, ToastModule, BadgeModule, TooltipModule, SkeletonModule
    ],
    providers: [MessageService],
    templateUrl: './inadimplencia.html',
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
        :host ::ng-deep .p-tabs-list {
            border: none;
            background: transparent;
        }
    `]
})
export class InadimplenciaComponent implements OnInit {
    loading: boolean = true;
    inadimplencias: any[] = [];
    dataCorte: Date = new Date(); // default hoje
    hoje: Date = new Date(); // data maxima permitida
    activeTab: string = '';

    constructor(
        private messageService: MessageService,
        private cdr: ChangeDetectorRef
    ) {}

    ngOnInit() {
        this.carregarDados();
    }

    setDiaAtual(dp?: any, event?: Event) {
        if (event) {
            event.stopPropagation();
            event.preventDefault();
        }
        setTimeout(() => {
            const now = new Date();
            this.hoje = now; // Update maxDate to avoid PrimeNG invalidation bug
            this.dataCorte = now;
            if (dp) {
                dp.writeValue(this.dataCorte);
                if (dp.updateInputfield) dp.updateInputfield();
                if (dp.hide) dp.hide();
            }
            this.onDataCorteChange();
            this.cdr.detectChanges();
        }, 10);
    }

    onDataCorteChange() {
        if (this.dataCorte) {
            this.carregarDados();
        }
    }

    async carregarDados() {
        this.loading = true;
        this.cdr.detectChanges();
        
        try {
            if (window.pywebview && window.pywebview.api) {
                const mes = String(this.dataCorte.getMonth() + 1).padStart(2, '0');
                const dia = String(this.dataCorte.getDate()).padStart(2, '0');
                const ano = this.dataCorte.getFullYear();
                const dataCorteStr = `${ano}-${mes}-${dia}`;
                
                const response = await window.pywebview.api.get_inadimplencia(dataCorteStr);
                
                if (response && response.status === 'success') {
                    let data = response.data || [];
                    data.forEach((unidade: any) => {
                        if (unidade.taxas) {
                            unidade.taxas = unidade.taxas.map((t: any) => {
                                if (t.vencimento) {
                                    const parts = t.vencimento.split('-');
                                    if (parts.length === 3) {
                                        t.vencimento_sort = t.vencimento;
                                        t.vencimento = `${parts[2]}/${parts[1]}/${parts[0]}`;
                                    } else {
                                        const p2 = t.vencimento.split('/');
                                        if (p2.length === 3) {
                                            t.vencimento_sort = `${p2[2]}-${p2[1]}-${p2[0]}`;
                                        }
                                    }
                                }
                                t.total = this.calcularTotal(t);
                                return t;
                            });
                        }
                    });
                    this.inadimplencias = data;
                    if (this.inadimplencias.length > 0) {
                        this.activeTab = this.inadimplencias[0].unidade;
                    }
                } else {
                    this.messageService.add({severity:'error', summary:'Erro', detail: response?.message || 'Falha ao carregar inadimplência'});
                }
            } else {
                console.warn("API pywebview não encontrada. O backend está rodando?");
                if (window.location.hostname === 'localhost') {
                    console.warn("Rodando localmente (ng serve). Entrando em Modo Simulação (Mocks).");
                    let mockData = [
                        {
                            unidade: '101',
                            taxas: [
                                { competencia: '2026-06', exibicao: 'JUN/2026', valor: 350.00, vencimento: '2026-06-15', descricao: 'Taxa Ordinária', multa: 7.00, juros_total: 10.50, dias_vencidos: 30 },
                                { competencia: '2026-07', exibicao: 'JUL/2026', valor: 350.00, vencimento: '2026-07-15', descricao: 'Taxa Ordinária', multa: 7.00, juros_total: 1.50, dias_vencidos: 5 }
                            ]
                        },
                        {
                            unidade: '202',
                            taxas: [
                                { competencia: '2026-05', exibicao: 'MAI/2026', valor: 400.00, vencimento: '2026-05-15', descricao: 'Taxa Ordinária', multa: 8.00, juros_total: 20.00, dias_vencidos: 61 },
                                { competencia: '2026-06', exibicao: 'JUN/2026', valor: 400.00, vencimento: '2026-06-15', descricao: 'Taxa Extra', multa: 8.00, juros_total: 12.00, dias_vencidos: 30 },
                                { competencia: '2026-07', exibicao: 'JUL/2026', valor: 400.00, vencimento: '2026-07-15', descricao: 'Taxa Ordinária', multa: 8.00, juros_total: 2.00, dias_vencidos: 5 }
                            ]
                        }
                    ];
                    
                    mockData.forEach((unidade: any) => {
                        if (unidade.taxas) {
                            unidade.taxas = unidade.taxas.map((t: any) => {
                                if (t.vencimento) {
                                    const parts = t.vencimento.split('-');
                                    if (parts.length === 3) {
                                        t.vencimento_sort = t.vencimento;
                                        t.vencimento = `${parts[2]}/${parts[1]}/${parts[0]}`;
                                    }
                                }
                                t.total = this.calcularTotal(t);
                                return t;
                            });
                        }
                    });
                    
                    this.inadimplencias = mockData;
                    
                    if (this.inadimplencias.length > 0) {
                        this.activeTab = this.inadimplencias[0].unidade;
                    }
                } else {
                    this.inadimplencias = [];
                }
            }
        } catch (error) {
            console.error(error);
            this.messageService.add({severity:'error', summary:'Erro', detail: 'Erro ao se comunicar com o backend'});
        } finally {
            this.loading = false;
            this.cdr.detectChanges();
        }
    }

    getAvatarColor(competencia: string): string {
        const colors = ['#f43f5e', '#ec4899', '#d946ef', '#a855f7', '#8b5cf6', '#6366f1', '#3b82f6', '#0ea5e9', '#06b6d4', '#14b8a6', '#10b981', '#22c55e', '#84cc16', '#eab308', '#f59e0b', '#f97316'];
        
        if (!competencia) return colors[0];
        let hash = 0;
        for (let i = 0; i < competencia.length; i++) {
            hash = competencia.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        const index = Math.abs(hash) % colors.length;
        return colors[index];
    }
    
    getAvatarLabelMes(competencia: string): string {
        if (!competencia || competencia.length < 7) return '--';
        return competencia.substring(5, 7);
    }
    
    calcularTotal(taxa: any): number {
        return (taxa.valor || 0) + (taxa.multa || 0) + (taxa.juros_total || 0);
    }
    
    somarColuna(unidade: any, campo: string): number {
        if (!unidade || !unidade.taxas) return 0;
        if (campo === 'total') {
            return unidade.taxas.reduce((acc: number, t: any) => acc + this.calcularTotal(t), 0);
        }
        return unidade.taxas.reduce((acc: number, t: any) => acc + (t[campo] || 0), 0);
    }
}
