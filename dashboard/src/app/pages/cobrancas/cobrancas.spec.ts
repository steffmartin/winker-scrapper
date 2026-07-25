import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CobrancasComponent } from './cobrancas';
import { MessageService, ConfirmationService } from 'primeng/api';
import { ChangeDetectorRef } from '@angular/core';

describe('CobrancasComponent (Dialogs)', () => {
    let component: CobrancasComponent;
    let fixture: ComponentFixture<CobrancasComponent>;

    beforeEach(async () => {
        // Mock the pywebview API for the tests
        (window as any).pywebview = {
            api: {
                get_condominio_config: jasmine.createSpy().and.returnValue(Promise.resolve({ status: 'success', data: { condominio: {} } })),
                get_taxas_comuns: jasmine.createSpy().and.returnValue(Promise.resolve({ status: 'success', data: [] })),
                get_taxas_individuais: jasmine.createSpy().and.returnValue(Promise.resolve({ status: 'success', data: [] }))
            }
        };

        await TestBed.configureTestingModule({
            imports: [CobrancasComponent],
            providers: [MessageService, ConfirmationService, ChangeDetectorRef]
        }).compileComponents();
    });

    beforeEach(() => {
        fixture = TestBed.createComponent(CobrancasComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should open taxa dialog for adding a new taxa (default type C)', () => {
        component.addTaxa();
        expect(component.currentTaxaTipo).toBe('C');
        expect(component.currentTaxaData).toBeNull();
        expect(component.displayDialog).toBeTrue();
    });

    it('should open taxa dialog for editing a common taxa', () => {
        const mockTaxa = { id: 1, tipo: 'C', descricao: 'Taxa Teste' };
        component.editTaxa(mockTaxa);
        expect(component.currentTaxaData).toEqual(mockTaxa);
        expect(component.displayDialog).toBeTrue();
        expect(component.displayDialogRenegociacao).toBeFalse();
    });

    it('should open renegociacao dialog for editing a renegotiation taxa (tipo P or R)', () => {
        const mockTaxa = { id: 2, tipo: 'P', renegociacao_id: 10, descricao: 'Parcela Renegociação' };
        component.editTaxa(mockTaxa);
        expect(component.currentRenegociacaoId).toBe(10);
        expect(component.displayDialogRenegociacao).toBeTrue();
        expect(component.displayDialog).toBeFalse();
    });

    it('should open renegociacao dialog for adding a new renegotiation', () => {
        component.addRenegociacao();
        expect(component.currentRenegociacaoId).toBeUndefined();
        expect(component.displayDialogRenegociacao).toBeTrue();
    });

    it('should reload lists on dialog save', () => {
        spyOn(component, 'loadTaxasIndividuais');
        spyOn(component, 'loadTaxasComuns');
        
        component.activeTab = 'individuais';
        component.onDialogSave();
        expect(component.loadTaxasIndividuais).toHaveBeenCalled();
        
        component.activeTab = 'comuns';
        component.onDialogSave();
        expect(component.loadTaxasComuns).toHaveBeenCalled();
    });
});
