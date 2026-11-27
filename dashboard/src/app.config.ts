import { provideHttpClient, withFetch } from '@angular/common/http';
import { ApplicationConfig, provideZonelessChangeDetection, provideAppInitializer, inject, LOCALE_ID } from '@angular/core';
import { provideRouter, withEnabledBlockingInitialNavigation, withInMemoryScrolling, withHashLocation } from '@angular/router';
import { registerLocaleData } from '@angular/common';
import localePt from '@angular/common/locales/pt';
registerLocaleData(localePt);

import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { appRoutes } from './app.routes';
import { LayoutService } from './app/layout/service/layout.service';
import { applyLayoutTheme } from './app/layout/theme';

export const appConfig: ApplicationConfig = {
    providers: [
        { provide: LOCALE_ID, useValue: 'pt-BR' },
        provideRouter(appRoutes, withHashLocation(), withInMemoryScrolling({ anchorScrolling: 'enabled', scrollPositionRestoration: 'enabled' }), withEnabledBlockingInitialNavigation()),
        provideHttpClient(withFetch()),
        provideZonelessChangeDetection(),
        providePrimeNG({ 
            theme: { preset: Aura, options: { darkModeSelector: '.app-dark' } },
            translation: {
                firstDayOfWeek: 0,
                dayNames: ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
                dayNamesShort: ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"],
                dayNamesMin: ["Do", "Se", "Te", "Qu", "Qu", "Se", "Sa"],
                monthNames: ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
                monthNamesShort: ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
                today: "Hoje",
                clear: "Limpar",
                dateFormat: "dd/mm/yy",
                weekHeader: "Sm"
            }
        }),
        provideAppInitializer(() => {
            const layoutService = inject(LayoutService);
            return new Promise<void>((resolve) => {
                const checkApi = setInterval(async () => {
                    const win = window as any;
                    if (win.pywebview && win.pywebview.api) {
                        clearInterval(checkApi);
                        try {
                            const response = await win.pywebview.api.get_preferencias();
                            if (response && response.status === 'success' && response.data) {
                                const pref = response.data;
                                layoutService.layoutConfig.update(config => ({
                                    ...config,
                                    darkTheme: pref.modo_escuro === 1,
                                    primary: pref.cor_primaria || config.primary,
                                    surface: pref.cor_superficie || config.surface,
                                    preset: pref.tema_preset || config.preset,
                                    menuMode: pref.modo_menu || config.menuMode
                                }));
                            }
                        } catch (e) {
                            console.error('Erro ao carregar preferências:', e);
                        }

                        applyLayoutTheme(layoutService.layoutConfig());

                        resolve();

                        setTimeout(async () => {
                            try {
                                if (win.pywebview?.api?.app_ready) {
                                    await win.pywebview.api.app_ready();
                                }
                            } catch (_) { /* splash já pode ter sido fechada */ }
                        }, 50);
                    }
                }, 50);

                // Fallback para desenvolvimento web ou falha do pywebview
                setTimeout(() => {
                    clearInterval(checkApi);
                    applyLayoutTheme(layoutService.layoutConfig());
                    resolve();
                }, 3000);
            });
        })
    ]
};
