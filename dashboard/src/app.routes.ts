import { Routes } from '@angular/router';
import { AppLayout } from './app/layout/component/app.layout';
import { Dashboard } from './app/pages/dashboard/dashboard';
import { Notfound } from './app/pages/notfound/notfound';

export const appRoutes: Routes = [
    {
        path: '',
        component: AppLayout,
        children: [
            { path: '', component: Dashboard },
            { 
                path: 'configuracoes', 
                loadComponent: () => import('./app/pages/configuracoes/configuracoes').then(m => m.ConfiguracoesComponent),
                canDeactivate: [(component: any) => {
                    return component.canDeactivate ? component.canDeactivate() : true;
                }]
            }
        ]
    },
    { path: 'notfound', component: Notfound },
    { path: '**', redirectTo: '/notfound' }
];
