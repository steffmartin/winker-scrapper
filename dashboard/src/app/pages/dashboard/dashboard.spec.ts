import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Dashboard } from './dashboard';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

describe('Dashboard', () => {
    let component: Dashboard;
    let fixture: ComponentFixture<Dashboard>;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [Dashboard, CommonModule],
            providers: [
                {
                    provide: ActivatedRoute,
                    useValue: {
                        snapshot: { paramMap: { get: () => null } }
                    }
                }
            ]
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
                get_dashboard_kpis: () => Promise.resolve({ status: 'success', data: {} }),
                get_transacoes: () => Promise.resolve({ status: 'success', data: { tree: [] } })
            } 
        };
        
        fixture.detectChanges();
        
        expect(component.isMockMode).toBeFalse();
        
        (window as any).pywebview = undefined;
    });

    it('should correctly expand 1 level (mes expanded, tipo collapsed)', () => {
        component.nodes = [
            {
                data: { tipo_node: 'mes' },
                expanded: false,
                children: [
                    {
                        data: { tipo_node: 'tipo' },
                        expanded: false,
                        children: [
                            { data: { tipo_node: 'categoria' }, expanded: false }
                        ]
                    }
                ]
            }
        ];
        
        component.expandLevels(1);
        
        expect(component.nodes[0].expanded).toBeTrue(); // Mes expanded
        expect(component.nodes[0].children![0].expanded).toBeFalse(); // Tipo collapsed
    });
});
