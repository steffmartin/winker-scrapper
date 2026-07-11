import { Component, inject, OnInit, OnDestroy, ChangeDetectorRef, ViewChild } from '@angular/core';
import { MenuItem } from 'primeng/api';
import { Subscription } from 'rxjs';
import { RouterModule, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { StyleClassModule } from 'primeng/styleclass';
import { AppConfigurator } from './app.configurator';
import { LayoutService } from '@/app/layout/service/layout.service';
import { SkeletonModule } from 'primeng/skeleton';
import { OverlayBadgeModule } from 'primeng/overlaybadge';
import { MenuModule } from 'primeng/menu';
import { TooltipModule } from 'primeng/tooltip';

@Component({
    selector: 'app-topbar',
    standalone: true,
    imports: [RouterModule, CommonModule, StyleClassModule, AppConfigurator, SkeletonModule, OverlayBadgeModule, MenuModule, TooltipModule],
    styles: [`
        ::ng-deep .icon-small {
            font-size: 0.5rem !important;
        }
    `],
    template: ` <div class="layout-topbar !bg-gradient-to-r !from-indigo-50/50 !to-blue-50/50 !border-b !border-indigo-100/50 dark:!from-slate-900/50 dark:!to-indigo-900/50 dark:!border-slate-800">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" (click)="layoutService.onMenuToggle()">
                <i class="pi pi-bars"></i>
            </button>
            <a class="layout-topbar-logo" routerLink="/">
                <i class="pi pi-building text-primary mr-2" style="font-size: 2rem"></i>
                <span *ngIf="condoName">{{ condoName }}</span>
                <p-skeleton *ngIf="!condoName" width="10rem" height="1.5rem"></p-skeleton>
            </a>
        </div>

        <div class="layout-topbar-actions">
            <div class="layout-config-menu">
                <button type="button" class="layout-topbar-action" (click)="toggleDarkMode()">
                    <i class="pi pi-sun dark:!hidden"></i>
                    <i class="pi pi-moon !hidden dark:!inline-block"></i>
                </button>
                <div class="relative">
                    @defer (on idle) {
                        <button
                            class="layout-topbar-action layout-topbar-action-highlight"
                            pStyleClass="@next"
                            enterFromClass="hidden"
                            enterActiveClass="animate-scalein"
                            leaveToClass="hidden"
                            leaveActiveClass="animate-fadeout"
                            [hideOnOutsideClick]="true"
                        >
                            <i class="pi pi-palette"></i>
                        </button>
                        <app-configurator />
                    }
                </div>
            </div>

            <button class="layout-topbar-menu-button layout-topbar-action" pStyleClass="@next" enterFromClass="hidden" enterActiveClass="animate-scalein" leaveToClass="hidden" leaveActiveClass="animate-fadeout" [hideOnOutsideClick]="true">
                <i class="pi pi-ellipsis-v"></i>
            </button>

            <div class="layout-topbar-menu hidden lg:block">
                <div class="layout-topbar-menu-content">
                    <button type="button" class="layout-topbar-action" routerLink="/revisao"
                            [pTooltip]="'Há ' + pendenciasCount + ' registros para revisar'" tooltipPosition="bottom">
                        <p-overlayBadge [value]="pendenciasCount.toString()" badgeSize="small" *ngIf="pendenciasCount > 0">
                            <i class="pi pi-check-square"></i>
                        </p-overlayBadge>
                        <i class="pi pi-check-square" *ngIf="pendenciasCount === 0"></i>
                        <span>Pendências</span>
                    </button>
                    <button type="button" class="layout-topbar-action" (click)="toggleUserMenu($event)">
                        <i class="pi pi-user"></i>
                        <span>Profile</span>
                    </button>
                    @defer (on idle) {
                        <p-menu #userMenu [model]="userMenuItems" [popup]="true"></p-menu>
                    }
                </div>
            </div>
        </div>
    </div>`
})
export class AppTopbar implements OnInit, OnDestroy {
    items!: MenuItem[];
    reviewSub!: Subscription;
    userMenuItems: MenuItem[] = [];
    condominios: any[] = [];
    currentCondoId: string | null = null;
    condoName: string | null = null;
    pendenciasCount: number = 0;

    @ViewChild('userMenu') userMenu: any;

    layoutService = inject(LayoutService);
    cdr = inject(ChangeDetectorRef);
    router = inject(Router);

    ngOnInit() {
        this.loadCondoData();
        this.reviewSub = this.layoutService.onReviewSaved.subscribe(() => {
            this.fetchFromApi();
        });
    }

    ngOnDestroy() {
        if (this.reviewSub) {
            this.reviewSub.unsubscribe();
        }
    }

    loadCondoData() {
        if ((window as any).pywebview && (window as any).pywebview.api) {
            this.fetchFromApi();
        } else {
            window.addEventListener('pywebviewready', () => {
                this.fetchFromApi();
            });

            setTimeout(() => {
                if (!this.condoName) {
                    if ((window as any).pywebview && (window as any).pywebview.api) {
                        this.fetchFromApi();
                    } else if (window.location.hostname === 'localhost') {
                        this.condoName = 'Condomínio (Mock)';
                        this.cdr.detectChanges();
                    } else {
                        setTimeout(() => {
                            if (!this.condoName) {
                                console.error('PyWebView falhou na Topbar. Mantendo skeleton de título.');
                            }
                        }, 5000);
                    }
                }
            }, 1000);
        }
    }

    fetchFromApi() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_nome_condominio().then((res: any) => {
                if (res.status === 'success' && res.data && res.data.nome) {
                    this.condoName = res.data.nome;
                    this.cdr.detectChanges();
                }
            }).catch(() => {
                console.error('Falha ao buscar condomínio na Topbar.');
            });
            pywebview.api.get_pendencias_revisao_count().then((res: any) => {
                if (res.status === 'success' && res.data) {
                    this.pendenciasCount = res.data.count || 0;
                } else {
                    this.pendenciasCount = 0;
                }
                this.cdr.detectChanges();
            });
        } else if (window.location.hostname === 'localhost') {
            // MOCK MODE
            if (typeof (window as any).__mockHasInconsistencies === 'undefined') {
                (window as any).__mockHasInconsistencies = Math.random() > 0.5;
            }
            setTimeout(() => {
                if (!this.currentCondoId) this.currentCondoId = '1';
                this.condoName = this.currentCondoId === '1' ? 'Condomínio Residencial Alpha (Mock)' :
                                 this.currentCondoId === '2' ? 'Edifício Beta (Mock)' : 'Vila Gama (Mock)';
                this.pendenciasCount = (window as any).__mockHasInconsistencies ? 12 : 0;
                this.cdr.detectChanges();
            }, 500);
        }
    }

    toggleUserMenu(event: Event) {
        if (!this.userMenu) {
            console.warn('O menu ainda está sendo carregado via @defer.');
            return;
        }

        if (this.condominios.length > 0) {
            this.userMenu.toggle(event);
            return;
        }

        this.userMenuItems = [{ label: 'Carregando...', icon: 'pi pi-spinner pi-spin' }];
        this.userMenu.toggle(event);

        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_condominios().then((res: any) => {
                if (res.status === 'success' && res.data) {
                    this.condominios = res.data;
                    this.currentCondoId = res.current_id;
                    this.buildUserMenu();
                } else {
                    this.buildUserMenu();
                }
                this.cdr.detectChanges();
            }).catch(() => {
                this.buildUserMenu();
                this.cdr.detectChanges();
            });
        } else if (window.location.hostname === 'localhost') {
            // MOCK MODE
            setTimeout(() => {
                this.condominios = [
                    { id: '1', nome: 'Condomínio Residencial Alpha (Mock)' },
                    { id: '2', nome: 'Edifício Beta (Mock)' },
                    { id: '3', nome: 'Vila Gama (Mock)' }
                ];
                if (!this.currentCondoId) this.currentCondoId = '1';
                this.buildUserMenu();
                this.cdr.detectChanges();
            }, 500);
        }
    }

    buildUserMenu() {
        this.userMenuItems = [];
        if (this.condominios.length > 0) {
            const condoItems = this.condominios.map(c => ({
                label: c.nome,
                icon: c.id === this.currentCondoId ? 'pi pi-circle-fill text-primary icon-small' : 'pi pi-circle text-surface-400 icon-small',
                styleClass: 'cursor-pointer',
                command: () => this.changeCondo(c.id)
            }));
            this.userMenuItems.push({
                label: 'Condomínios',
                items: condoItems
            });
            this.userMenuItems.push({ separator: true });
        }

        this.userMenuItems.push({
            label: 'Opções',
            items: [
                {
                    label: 'Sair',
                    icon: 'pi pi-sign-out text-red-500',
                    styleClass: 'cursor-pointer',
                    command: () => this.exitApp()
                }
            ]
        });
    }

    changeCondo(id: string) {
        if (id === this.currentCondoId) return;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.set_condominio(id).then((res: any) => {
                if (res.status === 'success') {
                    this.currentCondoId = id;
                    this.condominios = []; // Força recarregamento no próximo click do menu
                    this.fetchFromApi(); // Atualiza a topbar (nome, notificações)

                    // Recarrega os componentes da tela via Angular ao invés de window.location.reload()
                    // Isso evita o erro 500 do servidor webview interno
                    const currentUrl = this.router.url;
                    this.router.routeReuseStrategy.shouldReuseRoute = () => false;
                    this.router.onSameUrlNavigation = 'reload';
                    this.router.navigate([currentUrl]);
                } else {
                    alert('Erro interno ao trocar de condomínio: ' + res.message);
                }
            }).catch((err: any) => {
                alert('Erro 500 na API: ' + (err.message || JSON.stringify(err)));
                // Tenta o reload nativo como fallback
                window.location.reload();
            });
        } else if (window.location.hostname === 'localhost') {
            // MOCK MODE
            this.currentCondoId = id;
            this.condominios = [];
            this.fetchFromApi();
            
            const currentUrl = this.router.url;
            this.router.routeReuseStrategy.shouldReuseRoute = () => false;
            this.router.onSameUrlNavigation = 'reload';
            this.router.navigate([currentUrl]);
        }
    }

    exitApp() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api && pywebview.api.exit_app) {
            pywebview.api.exit_app();
        } else {
            window.close();
        }
    }

    toggleDarkMode() {
        this.layoutService.layoutConfig.update((state) => ({
            ...state,
            darkTheme: !state.darkTheme
        }));
    }
}
