import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { MenuItem } from 'primeng/api';
import { RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { StyleClassModule } from 'primeng/styleclass';
import { AppConfigurator } from './app.configurator';
import { LayoutService } from '@/app/layout/service/layout.service';
import { SkeletonModule } from 'primeng/skeleton';
import { OverlayBadgeModule } from 'primeng/overlaybadge';

@Component({
    selector: 'app-topbar',
    standalone: true,
    imports: [RouterModule, CommonModule, StyleClassModule, AppConfigurator, SkeletonModule, OverlayBadgeModule],
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
                    <button type="button" class="layout-topbar-action">
                        <p-overlayBadge [value]="inconsistenciesCount.toString()" badgeSize="small" *ngIf="inconsistenciesCount > 0">
                            <i class="pi pi-inbox"></i>
                        </p-overlayBadge>
                        <i class="pi pi-inbox" *ngIf="inconsistenciesCount === 0"></i>
                        <span>Notificações</span>
                    </button>
                    <button type="button" class="layout-topbar-action">
                        <i class="pi pi-user"></i>
                        <span>Profile</span>
                    </button>
                </div>
            </div>
        </div>
    </div>`
})
export class AppTopbar implements OnInit {
    items!: MenuItem[];
    condoName: string | null = null;
    inconsistenciesCount: number = 0;

    layoutService = inject(LayoutService);
    cdr = inject(ChangeDetectorRef);

    ngOnInit() {
        this.loadCondoData();
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
            pywebview.api.get_condominio().then((res: any) => {
                if (res.status === 'success' && res.data && res.data.nome) {
                    this.condoName = res.data.nome;
                    this.cdr.detectChanges();
                }
            }).catch(() => {
                console.error('Falha ao buscar condomínio na Topbar.');
            });
            pywebview.api.get_inconsistencies_count().then((res: any) => {
                if (res.status === 'success' && res.data) {
                    this.inconsistenciesCount = res.data.count || 0;
                } else {
                    this.inconsistenciesCount = 0;
                }
                this.cdr.detectChanges();
            });
        }
    }

    toggleDarkMode() {
        this.layoutService.layoutConfig.update((state) => ({
            ...state,
            darkTheme: !state.darkTheme
        }));
    }
}
