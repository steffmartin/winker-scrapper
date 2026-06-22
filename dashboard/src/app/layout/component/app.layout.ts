import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AppTopbar } from './app.topbar';
import { LayoutService } from '@/app/layout/service/layout.service';

@Component({
    selector: 'app-layout',
    standalone: true,
    imports: [CommonModule, AppTopbar, RouterModule],
    template: `<div class="layout-wrapper" [ngClass]="containerClass()">
        <app-topbar></app-topbar>
        <div class="layout-main-container">
            <div class="layout-main">
                <router-outlet></router-outlet>
            </div>
        </div>
    </div> `
})
export class AppLayout {
    layoutService = inject(LayoutService);

    containerClass = computed(() => {
        return {
            'layout-static': true,
            'layout-static-inactive': true
        };
    })
}
