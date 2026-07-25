import { ComponentFixture, TestBed } from '@angular/core/testing';
import { InadimplenciaComponent } from './inadimplencia';
import { MessageService } from 'primeng/api';
import { ChangeDetectorRef } from '@angular/core';

describe('InadimplenciaComponent (Dialogs and Context Menu)', () => {
    let component: InadimplenciaComponent;
    let fixture: ComponentFixture<InadimplenciaComponent>;

    beforeEach(async () => {
        (window as any).pywebview = {
            api: {
                get_inadimplencia: jasmine.createSpy().and.returnValue(Promise.resolve({ status: 'success', data: [] }))
            }
        };

        await TestBed.configureTestingModule({
            imports: [InadimplenciaComponent],
            providers: [MessageService, ChangeDetectorRef]
        }).compileComponents();
    });

    beforeEach(() => {
        fixture = TestBed.createComponent(InadimplenciaComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should select row if right-clicked row is not in current selection', () => {
        const mockCm = { show: jasmine.createSpy() };
        const mockEvent = new MouseEvent('contextmenu');
        
        component.selectedTaxas = [];
        component.contextMenuSelection = { id: 1, competencia: '2026-07' };
        
        component.onContextMenu(mockEvent, mockCm, '101');
        
        expect(component.selectedTaxas.length).toBe(1);
        expect(component.selectedTaxas[0].id).toBe(1);
        expect(mockCm.show).toHaveBeenCalledWith(mockEvent);
    });

    it('should populate context menu with "Nova Renegociação"', () => {
        const mockCm = { show: jasmine.createSpy() };
        component.selectedTaxas = [{ id: 1, competencia: '2026-07' }, { id: 2, competencia: '2026-08' }];
        
        component.onContextMenu(new MouseEvent('contextmenu'), mockCm, '101');
        
        expect(component.contextMenuItems.length).toBe(1);
        expect(component.contextMenuItems[0].label).toBe('Nova Renegociação');
    });

    it('should populate context menu with "Novo Desconto" only if exactly one taxa is selected', () => {
        const mockCm = { show: jasmine.createSpy() };
        
        // One taxa selected
        component.selectedTaxas = [{ id: 1, competencia: '2026-07' }];
        component.onContextMenu(new MouseEvent('contextmenu'), mockCm, '101');
        expect(component.contextMenuItems.length).toBe(2);
        expect(component.contextMenuItems[1].label).toBe('Novo Desconto');
        
        // Two taxas selected
        component.selectedTaxas = [{ id: 1, competencia: '2026-07' }, { id: 2, competencia: '2026-08' }];
        component.onContextMenu(new MouseEvent('contextmenu'), mockCm, '101');
        expect(component.contextMenuItems.length).toBe(1); // Only Nova Renegociação
    });

    it('should open Renegociacao dialog with correct auto-fill data', () => {
        component.selectedTaxas = [
            { id: 1, competencia: '2026-01' },
            { id: 2, competencia: '2026-03' }
        ];
        
        component.openRenegociacaoDialog('102');
        
        expect(component.showRenegociacaoDialog).toBeTrue();
        expect(component.selectedApartamento).toBe('102');
        expect(component.selectedTaxasIds).toEqual([1, 2]);
        
        expect(component.selectedCompetenciaRange.length).toBe(2);
        expect(component.selectedCompetenciaRange[0].getFullYear()).toBe(2026);
        expect(component.selectedCompetenciaRange[0].getMonth()).toBe(0); // Jan
        expect(component.selectedCompetenciaRange[1].getFullYear()).toBe(2026);
        expect(component.selectedCompetenciaRange[1].getMonth()).toBe(2); // Mar
    });

    it('should open Desconto dialog with correct auto-fill data', () => {
        component.selectedTaxas = [{ id: 5, competencia: '2026-05' }];
        
        component.openDescontoDialog('103');
        
        expect(component.showDescontoDialog).toBeTrue();
        expect(component.selectedApartamento).toBe('103');
        expect(component.selectedCompetencia).toBe('2026-05');
        expect(component.selectedTaxaId).toBe(5);
    });

    it('should trigger reload on dialog save', () => {
        spyOn(component, 'carregarDados');
        component.onDialogSave();
        expect(component.carregarDados).toHaveBeenCalled();
    });
});
