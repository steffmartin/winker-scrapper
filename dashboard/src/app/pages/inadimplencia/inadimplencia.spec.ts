import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InadimplenciaComponent } from './inadimplencia';

describe('InadimplenciaComponent', () => {
    let fixture: ComponentFixture<InadimplenciaComponent>;
    let component: InadimplenciaComponent;

    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [InadimplenciaComponent] }).compileComponents();
        fixture = TestBed.createComponent(InadimplenciaComponent);
        component = fixture.componentInstance;
    });

    afterEach(() => {
        delete window.pywebview;
    });

    it('exibe a conciliação pendente sem informar ausência de inadimplência', async () => {
        const consulta = jasmine.createSpy('get_inadimplencia').and.returnValues(
            Promise.resolve({ status: 'success', data: [] }),
            Promise.resolve({ status: 'error', message: 'Conciliação pendente para a unidade 101' })
        );
        window.pywebview = { api: { get_inadimplencia: consulta } };

        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain('Sem Inadimplência');

        await component.carregarDados();
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain('Conciliação pendente para a unidade 101');
        expect(fixture.nativeElement.textContent).not.toContain('Sem Inadimplência');
        expect(component.inadimplencias).toEqual([]);
    });
});
