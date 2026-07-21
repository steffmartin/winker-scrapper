import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { AppMenuitem } from './app.menuitem';

@Component({
    selector: 'app-menu',
    standalone: true,
    imports: [CommonModule, AppMenuitem, RouterModule],
    template: `<ul class="layout-menu">
        @for (item of model; track item.label) {
            @if (!item.separator) {
                <li app-menuitem [item]="item" [root]="true"></li>
            } @else {
                <li class="menu-separator"></li>
            }
        }
    </ul> `,
})
export class AppMenu {
    model: MenuItem[] = [];

    ngOnInit() {
        this.model = [
            {
                label: 'Home',
                items: [
                    { label: 'Dashboard', icon: 'pi pi-fw pi-home', routerLink: ['/'] },
                    { label: 'Inadimplência', icon: 'pi pi-fw pi-exclamation-triangle', routerLink: ['/inadimplencia'] }
                ]
            },
            {
                label: 'Gestão e Operações',
                items: [
                    { label: 'Revisão', icon: 'pi pi-fw pi-check-square', routerLink: ['/revisao'] },
                    { label: 'Cobranças', icon: 'pi pi-fw pi-money-bill', routerLink: ['/cobrancas'] },
                    { label: 'Configurações', icon: 'pi pi-fw pi-cog', routerLink: ['/configuracoes'] }
                ]
            }
        ];
    }
}
