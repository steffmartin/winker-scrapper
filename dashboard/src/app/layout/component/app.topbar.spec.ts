import { TestBed } from '@angular/core/testing';
import { AppTopbar } from './app.topbar';
import { ChangeDetectorRef } from '@angular/core';
import { LayoutService } from '@/app/layout/service/layout.service';
describe('AppTopbar', () => {
    let component: AppTopbar;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [
                LayoutService,
                { provide: ChangeDetectorRef, useValue: { detectChanges: () => {} } }
            ]
        });
        
        TestBed.runInInjectionContext(() => {
            component = new AppTopbar();
        });
    });

    afterEach(() => {
        delete (window as any).pywebview;
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should load condo data and inconsistencies from pywebview when available', async () => {
        (window as any).pywebview = {
            api: {
                get_nome_condominio: () => Promise.resolve({ status: 'success', data: { nome: 'Condominio Pywebview' } }),
                get_inconsistencies_count: () => Promise.resolve({ status: 'success', data: { count: 5 } })
            }
        };

        component.loadCondoData();
        
        // Wait for promise resolution
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(component.condoName).toBe('Condominio Pywebview');
        expect(component.inconsistenciesCount).toBe(5);
    });
});
