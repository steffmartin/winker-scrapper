import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CobrancasComponent } from './cobrancas';

describe('Renegociação de cobranças', () => {
    let fixture: ComponentFixture<CobrancasComponent>;
    let component: CobrancasComponent;

    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [CobrancasComponent] }).compileComponents();
        fixture = TestBed.createComponent(CobrancasComponent);
        component = fixture.componentInstance;
        component.dataRenegociacaoDate = new Date(2026, 10, 15, 12);
        component.vencimentoPrimeiraParcelaDate = new Date(2026, 10, 20);
        component.quantidadeParcelas = 2;
        component.taxa_renegociacao_config = 5;
    });

    afterEach(() => {
        delete (window as any).pywebview;
    });

    it('oferece parcelas anteriores junto com taxas normais na nova renegociação', async () => {
        const buscar = jasmine.createSpy('get_taxas_por_apartamento').and.resolveTo({
            status: 'success', data: [
                { id: 1, tipo: 'C', descricao: 'Taxa', exibicao: 'NOV/2026', valor_original: 100 },
                { id: 2, tipo: 'P', descricao: 'Parcela', exibicao: 'NOV/2026', valor_original: 50 }
            ]
        });
        (window as any).pywebview = { api: { get_taxas_por_apartamento: buscar } };
        component.currentRenegociacao = { apartamento: '101' };
        component.apartamentos = ['101'];
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), new Date(2026, 10, 1)];
        component.onRenegociacaoFormChange();
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith('101', ['2026-11', '2026-11'], ['C', 'E', 'I', 'P', 'D']);
        expect(component.taxasOriginaisParaRenegociacao.map(t => t.id)).toEqual([1, 2]);
    });

    it('aplica o desconto e os percentuais reduzidos à taxa vinculada', () => {
        component.tipo_juros_multa = 'N';
        component.taxasOriginaisSelecionadas = [
            { id: 1, tipo: 'C', vencimento: '14/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 3 },
            { id: 2, tipo: 'D', taxa_id: 1, valor_original: 20, multa_percentual: 1, juros_mes_percentual: 1 }
        ];
        expect(component.descontosComTaxasSelecionadas).toBeTrue();
        expect(component.selectedTaxasDetalhesSum.desconto).toBe(20);
        expect(component.selectedTaxasSum).toBeCloseTo(80 + 0.8 + 80 * 0.02 / 30, 10);
        component.taxasOriginaisSelecionadas.shift();
        expect(component.descontosComTaxasSelecionadas).toBeFalse();
        expect(component.isRenegociacaoValid).toBeFalse();
    });

    it('reabre uma renegociação com a parcela anterior selecionada, sem oferecer suas próprias parcelas', async () => {
        const buscar = jasmine.createSpy('get_taxas_por_apartamento').and.resolveTo({ status: 'success', data: [
            { id: 2, tipo: 'P', renegociacao_id: 1, descricao: 'Parcela anterior', valor_original: 50 },
            { id: 3, tipo: 'P', renegociacao_id: 2, descricao: 'Parcela atual', valor_original: 50 }
        ] });
        (window as any).pywebview = { api: {
            get_taxas_por_apartamento: buscar,
            get_renegociacao: jasmine.createSpy().and.resolveTo({ status: 'success', data: {
                id: 2, apartamento: '101', data_renegociacao: '15/11/2026', competencia_inicial: '2026-11',
                competencia_final: '2026-11', taxas_originais: [{ taxa_id: 2 }], parcelas: []
            } })
        } };
        component.editRenegociacao(2);
        await Promise.resolve();
        await Promise.resolve();
        expect(component.taxasOriginaisParaRenegociacao.map(t => t.id)).toEqual([2]);
        expect(component.taxasOriginaisSelecionadas.map(t => t.id)).toEqual([2]);
    });

    for (const tipo of ['N', 'M', 'J']) {
        for (const vencimento of ['15/11/2026', '16/11/2026']) {
            it(`não cobra multa nem juros para vencimento ${vencimento}, cálculo ${tipo}`, () => {
                component.tipo_juros_multa = tipo;
                component.taxasOriginaisSelecionadas = [{
                    vencimento, valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1
                }];

                expect(component.getDiasAtraso(vencimento)).toBe(0);
                expect(component.selectedTaxasDetalhesSum.multa).toBe(0);
                expect(component.selectedTaxasDetalhesSum.juros).toBe(0);
                expect(component.selectedTaxasSum).toBe(100);
                component.onTaxasOriginaisChange();
                expect(component.despesasAdicionais).toBe(5);
                component.gerarParcelasRenegociacao();
                expect(component.parcelasGeradas.map(p => p.valor_original)).toEqual([52.5, 52.5]);
            });
        }
    }

    for (const cenario of [
        { tipo: 'N', multa: 2, juros: 100 * (1 / 30 / 100) },
        { tipo: 'M', multa: (100 + 100 * (1 / 30 / 100)) * 0.02, juros: 100 * (1 / 30 / 100) },
        { tipo: 'J', multa: 2, juros: 102 * (1 / 30 / 100) }
    ]) {
        it(`mantém a fórmula ${cenario.tipo} para um dia de atraso`, () => {
            component.tipo_juros_multa = cenario.tipo;
            component.taxasOriginaisSelecionadas = [{
                vencimento: '14/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1
            }];

            expect(component.getDiasAtraso('14/11/2026')).toBe(1);
            expect(component.selectedTaxasDetalhesSum.multa).toBeCloseTo(cenario.multa, 10);
            expect(component.selectedTaxasDetalhesSum.juros).toBeCloseTo(cenario.juros, 10);
            expect(component.selectedTaxasSum).toBeCloseTo(100 + cenario.multa + cenario.juros, 10);
        });
    }

    it('aplica encargos somente às taxas vencidas quando a seleção é mista', () => {
        component.tipo_juros_multa = 'N';
        component.taxasOriginaisSelecionadas = [
            { vencimento: '14/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1 },
            { vencimento: '16/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1 }
        ];

        const juros = 100 * (1 / 30 / 100);
        expect(component.selectedTaxasDetalhesSum.multa).toBe(2);
        expect(component.selectedTaxasDetalhesSum.juros).toBeCloseTo(juros, 10);
        expect(component.selectedTaxasDetalhesSum.geral).toBeCloseTo(202 + juros, 10);
        expect(component.selectedTaxasSum).toBeCloseTo(202 + juros, 10);
    });

    it('envia as parcelas sem multa indevida ao salvar uma renegociação', async () => {
        const salvar = jasmine.createSpy('salvar_renegociacao').and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { salvar_renegociacao: salvar } };
        spyOn(component, 'loadTaxasIndividuais');
        component.currentRenegociacao = { apartamento: '101', numero: '123' };
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), new Date(2026, 10, 1)];
        component.taxasOriginaisSelecionadas = [{
            id: 123, vencimento: '16/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1
        }];

        component.onTaxasOriginaisChange();
        component.gerarParcelasRenegociacao();
        expect(component.isRenegociacaoValid).toBeTrue();
        component.saveRenegociacao();

        expect(salvar).toHaveBeenCalledTimes(1);
        const payload = salvar.calls.mostRecent().args[0];
        expect(payload.taxas_originais).toEqual([123]);
        expect(payload.despesas_adicionais).toBe(5);
        expect(payload.parcelas.map((p: any) => p.valor_original)).toEqual([52.5, 52.5]);
        await Promise.resolve();
    });
});
