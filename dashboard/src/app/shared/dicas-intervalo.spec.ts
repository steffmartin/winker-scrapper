import { TestBed } from '@angular/core/testing';
import { DicaOrdenacaoComponent } from './dica-ordenacao.component';

describe('Dica de ordenação', () => {
    it('usa mensagem informativa e desaparece após 15 segundos', () => {
        jasmine.clock().install();
        const fixture = TestBed.createComponent(DicaOrdenacaoComponent);
        fixture.nativeElement.style.setProperty('--p-primary-color', 'rgb(20, 80, 160)');
        fixture.detectChanges();
        expect(parseFloat(getComputedStyle(fixture.nativeElement).bottom)).toBeGreaterThan(40);
        expect(fixture.nativeElement.querySelector('p-message').textContent).toContain('Ctrl');
        expect(fixture.nativeElement.querySelector('p-message').getAttribute('severity')).toBe('info');
        const estilo = getComputedStyle(fixture.nativeElement.querySelector('p-message'));
        expect(estilo.borderTopStyle).toBe('solid');
        expect(estilo.borderTopColor).toBe('rgb(20, 80, 160)');
        expect(fixture.nativeElement.querySelector('p-message button')).toBeNull();
        jasmine.clock().tick(14999); fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('p-message')).not.toBeNull();
        jasmine.clock().tick(1); fixture.detectChanges();
        expect(fixture.componentInstance.visivel()).toBeFalse();
        fixture.destroy();
        jasmine.clock().uninstall();
    });
});
