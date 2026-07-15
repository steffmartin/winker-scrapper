import { provideHttpClient, withFetch } from '@angular/common/http';
import { ApplicationConfig, provideZonelessChangeDetection, provideAppInitializer, inject, LOCALE_ID } from '@angular/core';
import { provideRouter, withEnabledBlockingInitialNavigation, withInMemoryScrolling, withHashLocation } from '@angular/router';
import { registerLocaleData } from '@angular/common';
import localePt from '@angular/common/locales/pt';
registerLocaleData(localePt);

import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { appRoutes } from './app.routes';
import { LayoutService } from './app/layout/service/layout.service';

const WinkerPreset = definePreset(Aura, {
    semantic: {
        primary: {
            50: '{blue.50}',
            100: '{blue.100}',
            200: '{blue.200}',
            300: '{blue.300}',
            400: '{blue.400}',
            500: '{blue.500}',
            600: '{blue.600}',
            700: '{blue.700}',
            800: '{blue.800}',
            900: '{blue.900}',
            950: '{blue.950}'
        },
        colorScheme: {
            light: {
                surface: {
                    0: '#ffffff',
                    50: '{slate.50}',
                    100: '{slate.100}',
                    200: '{slate.200}',
                    300: '{slate.300}',
                    400: '{slate.400}',
                    500: '{slate.500}',
                    600: '{slate.600}',
                    700: '{slate.700}',
                    800: '{slate.800}',
                    900: '{slate.900}',
                    950: '{slate.950}'
                }
            },
            dark: {
                surface: {
                    0: '#ffffff',
                    50: '{zinc.50}',
                    100: '{zinc.100}',
                    200: '{zinc.200}',
                    300: '{zinc.300}',
                    400: '{zinc.400}',
                    500: '{zinc.500}',
                    600: '{zinc.600}',
                    700: '{zinc.700}',
                    800: '{zinc.800}',
                    900: '{zinc.900}',
                    950: '{zinc.950}'
                }
            }
        }
    }
});

export const appConfig: ApplicationConfig = {
    providers: [
        { provide: LOCALE_ID, useValue: 'pt-BR' },
        provideRouter(appRoutes, withHashLocation(), withInMemoryScrolling({ anchorScrolling: 'enabled', scrollPositionRestoration: 'enabled' }), withEnabledBlockingInitialNavigation()),
        provideHttpClient(withFetch()),
        provideZonelessChangeDetection(),
        providePrimeNG({ 
            theme: { preset: WinkerPreset, options: { darkModeSelector: '.app-dark' } },
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
                    resolve();
                }, 3000);
            });
        })
    ]
};
