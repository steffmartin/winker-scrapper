import { Component, OnInit, ChangeDetectorRef, LOCALE_ID } from '@angular/core';
import { CommonModule, CurrencyPipe, DatePipe, registerLocaleData } from '@angular/common';
import { SkeletonModule } from 'primeng/skeleton';
import { ChipModule } from 'primeng/chip';
import localePt from '@angular/common/locales/pt';

registerLocaleData(localePt);

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [
        CommonModule,
        CurrencyPipe,
        SkeletonModule,
        ChipModule
    ],
    providers: [
        { provide: LOCALE_ID, useValue: 'pt-BR' }
    ],
    templateUrl: './dashboard.html'
})
export class Dashboard implements OnInit {
    isMockMode = false;
    loadingKpis = true;
    kpis: any = {
        inadimplencia: null,
        gestao: null,
        saldos: null,
        resumo_mes: null
    };

    sindicoName = 'Sem Síndico';
    conselheirosList: string[] = [];

    constructor(private cdr: ChangeDetectorRef) {}

    ngOnInit() {
        this.detectEnvironmentAndLoad();
    }

    detectEnvironmentAndLoad() {
        if ((window as any).pywebview && (window as any).pywebview.api) {
            this.isMockMode = false;
            this.fetchKpis((window as any).pywebview.api);
        } else {
            // Wait for the pywebviewready event
            window.addEventListener('pywebviewready', () => {
                this.isMockMode = false;
                this.fetchKpis((window as any).pywebview.api);
            });

            // Fallback for local development (ng serve)
            setTimeout(() => {
                if (this.loadingKpis) {
                    if ((window as any).pywebview && (window as any).pywebview.api) {
                        this.isMockMode = false;
                        this.fetchKpis((window as any).pywebview.api);
                    } else if (window.location.hostname === 'localhost') {
                        console.warn('Rodando localmente (ng serve). Entrando em Modo Simulação (Mocks).');
                        this.isMockMode = true;
                        this.loadMockKpis();
                    } else {
                        // Se não for localhost, espera mais tempo pelo pywebview
                        console.warn('Aguardando PyWebView carregar...');
                        setTimeout(() => {
                            if (this.loadingKpis) {
                                console.error('PyWebView falhou em carregar após 6 segundos. Mantendo interface em loading.');
                            }
                        }, 5000);
                    }
                }
            }, 1000);
        }
    }

    fetchKpis(api: any) {
        api.get_dashboard_kpis().then((response: any) => {
            if (response.status === 'success') {
                this.kpis = response.data;
                this.processMembers();
            } else {
                console.error('Erro ao buscar KPIs', response.message);
            }
            this.loadingKpis = false;
            this.cdr.detectChanges();
        }).catch((err: any) => {
            console.error('Erro na chamada da API', err);
            this.loadingKpis = false;
            this.cdr.detectChanges();
        });
    }

    processMembers() {
        const membros = this.kpis?.gestao?.membros || [];

        const sindico = membros.find((m: any) => m.cargo && m.cargo.toLowerCase().includes('síndico') && !m.cargo.toLowerCase().includes('sub'));
        if (sindico) {
            this.sindicoName = sindico.nome;
        } else if (membros.length > 0) {
            this.sindicoName = membros[0].nome;
        }

        const conselheiros = membros.filter((m: any) => m.cargo && m.cargo.toLowerCase().includes('conselh'));
        if (conselheiros.length > 0) {
            this.conselheirosList = conselheiros.map((c: any) => {
                const parts = c.nome.trim().split(' ');
                return parts[0];
            });
        } else {
            this.conselheirosList = [];
        }
    }

    loadMockKpis() {
        this.kpis = {
            inadimplencia: {
                valor: 2500.50,
                unidades: 3,
                data_corte: '2023-10-01'
            },
            gestao: {
                membros: [
                    { nome: 'Carlos Silva', cargo: 'Síndico' },
                    { nome: 'Ana Souza', cargo: 'Conselheiro' },
                    { nome: 'Pedro Álvares', cargo: 'Conselheiro' }
                ],
                administradora: {
                    nome: 'Admin Teste LTDA',
                    telefone: '(11) 9999-9999'
                }
            },
            saldos: {
                saldo_total: 0,
                contas: [
                    { nome: 'Conta Corrente Padrão', saldo: 0 },
                    { nome: 'Fundo de Reserva', saldo: 0 }
                ]
            },
            resumo_mes: {
                competencia: '10/2023',
                receita_total: 30000.00,
                despesa_total: 28000.00,
                resultado: 2000.00
            }
        };
        this.processMembers();
        this.loadingKpis = false;
        this.cdr.detectChanges();
    }
}
