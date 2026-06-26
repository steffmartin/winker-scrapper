import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Dashboard } from './dashboard';
import { CommonModule } from '@angular/common';

describe('Dashboard', () => {
    let component: Dashboard;
    let fixture: ComponentFixture<Dashboard>;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [Dashboard, CommonModule]
        }).compileComponents();

        fixture = TestBed.createComponent(Dashboard);
        component = fixture.componentInstance;
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should set mock mode if no pywebview is found', (done) => {
        (window as any).pywebview = undefined;

        
        fixture.detectChanges();
        
        setTimeout(() => {
            expect(component.isMockMode).toBeTrue();
            done();
        }, 1100);
    });

    it('should set success mode if pywebview is found immediately', () => {
        (window as any).pywebview = { 
            api: {
                get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {} })
            } 
        };
        
        fixture.detectChanges();
        
        expect(component.isMockMode).toBeFalse();
        
        (window as any).pywebview = undefined;
    });
});
