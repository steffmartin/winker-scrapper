import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CobrancasComponent } from './cobrancas';
import { By } from '@angular/platform-browser';
import { DatePicker } from 'primeng/datepicker';
import { DeferBlockState } from '@angular/core/testing';
import { ConfirmationService, MessageService } from 'primeng/api';

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

    it('carrega taxas por aba, calcula valor à vista e ordenação de vencimento', async () => {
        const buscar = jasmine.createSpy().and.resolveTo({ status: 'success', data: [
            { tipo: 'C', valor_original: 100, desconto_vista: 10, vencimento: '05/02/2025' }
        ] });
        (window as any).pywebview = { api: { get_taxas: buscar } };
        component.onTabChange('comuns');
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith(['C', 'E']);
        expect(component.taxasComuns[0].valor_a_vista).toBe(90);
        expect(component.taxasComuns[0].vencimento_sort).toBe('2025-02-05');
        component.onTabChange('individuais');
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith(['I', 'D', 'P']);
        expect(component.taxasIndividuaisLoaded).toBeTrue();
        expect(component.loadingIndividuais).toBeFalse();
    });

    it('inicia taxas e restaura datas ao editar uma cobrança', () => {
        component.addTaxa('E');
        expect(component.dialogTitle).toBe('Nova Taxa Extra');
        expect(component.mesesRepeticao).toBe(1);
        expect(component.currentTaxa.tipo).toBe('E');
        component.editTaxa({ tipo: 'I', competencia: '2025-02', vencimento: '15/02/2025', descricao: 'Garagem' });
        expect(component.isEdit).toBeTrue();
        expect(component.dialogTitle).toBe('Editar Taxa Individual');
        expect(component.competenciaDate).toEqual(new Date(2025, 1, 1));
        expect(component.vencimentoDate).toEqual(new Date(2025, 1, 15));
        expect(component.getAvatarLabelMes('2025-02')).toBe('02');
        expect(component.getTipoAvatarColor('I')).toBe('#10b981');
    });

    it('valida dados obrigatórios antes de inserir cobrança individual', () => {
        const inserir = jasmine.createSpy().and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { insert_taxa: inserir } };
        component.addTaxa('I');
        component.saveTaxa();
        component.competenciaDate = new Date(2025, 1, 1);
        component.saveTaxa();
        component.vencimentoDate = new Date(2025, 1, 15);
        component.saveTaxa();
        component.currentTaxa.descricao = 'Garagem';
        component.currentTaxa.valor_original = null;
        component.saveTaxa();
        component.currentTaxa.valor_original = 50;
        component.saveTaxa();
        component.currentTaxa.apartamento = '999';
        component.apartamentos = ['101'];
        component.saveTaxa();
        expect(inserir).not.toHaveBeenCalled();
    });

    it('atualiza cobrança existente e exige confirmação para excluir', async () => {
        const atualizar = jasmine.createSpy().and.resolveTo({ status: 'success' });
        const excluir = jasmine.createSpy().and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { update_taxa: atualizar, delete_taxa: excluir } };
        spyOn(component, 'loadTaxasComuns');
        component.editTaxa({ id: 7, tipo: 'C', competencia: '2025-01', vencimento: '15/01/2025',
            descricao: 'Condomínio', valor_original: 100 });
        component.mesesRepeticao = 12;
        component.saveTaxa();
        expect(atualizar).toHaveBeenCalledWith(7, jasmine.objectContaining({ competencia: '2025-01',
            vencimento: '15/01/2025', meses_repeticao: 1 }));
        await Promise.resolve();
        const confirmar = spyOn(fixture.debugElement.injector.get(ConfirmationService), 'confirm').and.callFake((opcao: any) => {
            opcao.accept();
            return fixture.debugElement.injector.get(ConfirmationService);
        });
        component.deleteTaxa();
        await Promise.resolve();
        expect(confirmar).toHaveBeenCalled();
        expect(excluir).toHaveBeenCalledOnceWith(7);
        expect(component.loadTaxasComuns).toHaveBeenCalledTimes(2);
    });

    it('mantém o calendário de competência aberto ao redimensionar durante a seleção', async () => {
        component.displayDialogRenegociacao = true;
        fixture.detectChanges();
        for (const bloco of await fixture.getDeferBlocks()) await bloco.render(DeferBlockState.Complete);
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        const seletor = fixture.debugElement.query(By.css('#ren-competencia')).injector.get(DatePicker);
        seletor.showOverlay();
        fixture.detectChanges(false);
        await fixture.whenStable();
        expect(seletor.overlayVisible).toBeTrue();
        seletor.onWindowResize();
        expect(seletor.overlayVisible).toBeTrue();
    });

    it('seleciona um intervalo e reabre com as competências existentes', async () => {
        component.displayDialogRenegociacao = true;
        fixture.detectChanges();
        for (const bloco of await fixture.getDeferBlocks()) await bloco.render(DeferBlockState.Complete);
        fixture.detectChanges(false);
        await fixture.whenStable();
        fixture.detectChanges(false);
        const seletor = fixture.debugElement.query(By.css('#ren-competencia')).injector.get(DatePicker);
        seletor.showOverlay();
        seletor.currentYear = 2026;
        seletor.onMonthSelect(new MouseEvent('click'), 0);
        expect(seletor.overlayVisible).toBeTrue();
        seletor.onMonthSelect(new MouseEvent('click'), 1);
        expect(component.competenciaRenegociacaoRange.map(d => d.getMonth())).toEqual([0, 1]);
        await new Promise(resolve => setTimeout(resolve, 180));
        seletor.showOverlay();
        expect(seletor.overlayVisible).toBeTrue();
        expect(seletor.isMonthSelected(0)).toBeTrue();
        expect(seletor.isMonthSelected(1)).toBeTrue();
    });

    it('preenche o vencimento do desconto ao selecionar a taxa somente se estiver vazio', () => {
        component.currentTaxa = { tipo: 'D', taxa_id: 1 };
        component.taxasParaDesconto = [{ id: 1, vencimento: '15/01/2023' }];
        component.vencimentoDate = null;
        component.onTaxaVinculadaChange();
        expect(component.vencimentoDate as Date | null).toEqual(new Date(2023, 0, 15));
        component.vencimentoDate = new Date(2023, 0, 20);
        component.onTaxaVinculadaChange();
        expect(component.vencimentoDate).toEqual(new Date(2023, 0, 20));
    });

    it('envia e reabre o vencimento próprio do desconto', async () => {
        const salvar = jasmine.createSpy('insert_taxa').and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { insert_taxa: salvar } };
        spyOn(component, 'loadTaxasIndividuais');
        component.currentTaxa = { tipo: 'D', taxa_id: 1, apartamento: '101', descricao: 'Desconto', valor_original: 20 };
        component.apartamentos = ['101'];
        component.taxasParaDesconto = [{ id: 1, valor_original: 100, desconto_vista: 0, multa_percentual: 0, juros_mes_percentual: 0 }];
        component.competenciaDate = new Date(2023, 0, 1);
        component.vencimentoDate = new Date(2023, 0, 20);
        component.saveTaxa();
        expect(salvar.calls.mostRecent().args[0].vencimento).toBe('20/01/2023');
        await Promise.resolve();
        component.editTaxa({ tipo: 'D', competencia: '2023-01', vencimento: '20/01/2023' });
        expect(component.vencimentoDate).toEqual(new Date(2023, 0, 20));
    });

    it('oferece parcelas anteriores junto com taxas normais na nova renegociação', async () => {
        const buscar = jasmine.createSpy('get_taxas_por_apartamento').and.resolveTo({
            status: 'success', data: [
                { id: 1, tipo: 'C', descricao: 'Taxa', exibicao: 'NOV/2026', valor_original: 100 },
                { id: 2, tipo: 'P', descricao: 'Parcela', exibicao: 'NOV/2026', valor_original: 50 },
                { id: 3, tipo: 'E', descricao: 'Extraordinária', exibicao: 'NOV/2026', valor_original: 75 }
            ]
        });
        (window as any).pywebview = { api: { get_taxas_por_apartamento: buscar } };
        component.currentRenegociacao = { apartamento: '101' };
        component.apartamentos = ['101'];
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), new Date(2026, 10, 1)];
        component.onRenegociacaoFormChange();
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith('101', ['2026-11', '2026-11'], ['C', 'E', 'I', 'P', 'D']);
        expect(component.taxasOriginaisParaRenegociacao.map(t => t.id)).toEqual([1, 2, 3]);
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

    it('reabre parcelas existentes com datas convertidas e valor à vista', async () => {
        const buscar = jasmine.createSpy().and.resolveTo({ status: 'success', data: [{ id: 10, descricao: 'Original', valor_original: 100 }] });
        (window as any).pywebview = { api: { get_taxas_por_apartamento: buscar,
            get_renegociacao: jasmine.createSpy().and.resolveTo({ status: 'success', data: {
                id: 2, apartamento: '101', numero: 'A', data_renegociacao: '15/11/2026',
                vencimento_primeira_parcela: '20/11/2026', competencia_inicial: '2026-10', competencia_final: '2026-11',
                quantidade_parcelas: 1, despesas_adicionais: 5, descontos_adicionais: 2,
                taxas_originais: [{ taxa_id: 10 }], parcelas: [{ descricao: 'Parcela 1', vencimento: '20/11/2026',
                    competencia: '2026-11', valor_original: 103, desconto_vista: 3 }] } }) } };
        component.editRenegociacao(2);
        await Promise.resolve();
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith('101', ['2026-10', '2026-11'], ['C', 'E', 'I', 'P', 'D']);
        expect(component.parcelasGeradas[0].vencimento).toEqual(new Date(2026, 10, 20));
        expect(component.parcelasGeradas[0].competencia).toEqual(new Date(2026, 10, 1));
        expect(component.parcelasGeradas[0].valor_a_vista).toBe(100);
        expect(component.taxasOriginaisSelecionadas.map(t => t.id)).toEqual([10]);
        expect(component.displayDialogRenegociacao).toBeTrue();
    });

    it('exclui renegociação após confirmação e recarrega cobranças individuais', async () => {
        const excluir = jasmine.createSpy().and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { delete_renegociacao: excluir } };
        const carregar = spyOn(component, 'loadTaxasIndividuais');
        const confirmacao = fixture.debugElement.injector.get(ConfirmationService);
        spyOn(confirmacao, 'confirm').and.callFake((opcao: any) => { opcao.accept(); return confirmacao; });
        component.currentRenegociacao = { id: 9 };
        component.displayDialogRenegociacao = true;
        component.deleteRenegociacao();
        await Promise.resolve();
        expect(excluir).toHaveBeenCalledOnceWith(9);
        expect(component.displayDialogRenegociacao).toBeFalse();
        expect(carregar).toHaveBeenCalled();
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

    it('inicializa com configuração do condomínio e comandos do menu de ações', async () => {
        const config = jasmine.createSpy('get_condominio_config').and.resolveTo({ status: 'success', data: {
            condominio: { apartamentos: ['101', '102'], tipo_juros_multa: 'M', taxa_renegociacao: 7.5 }
        } });
        const buscar = jasmine.createSpy('get_taxas').and.resolveTo({ status: 'success', data: [] });
        (window as any).pywebview = { api: { get_condominio_config: config, get_taxas: buscar } };
        fixture.detectChanges();
        await Promise.resolve();
        await Promise.resolve();
        expect(component.apartamentos).toEqual(['101', '102']);
        expect(component.tipo_juros_multa).toBe('M');
        expect(component.taxa_renegociacao_config).toBe(7.5);
        expect(component.speedDialComunsItems[0].command).toBeDefined();
        expect(component.speedDialComunsItems[1].command).toBeDefined();
        expect(component.speedDialItems.map(i => i.label)).toEqual(['Nova Taxa Individual', 'Novo Desconto', 'Nova Renegociação']);
        component.speedDialComunsItems[0].command!({} as any);
        expect(component.dialogTitle).toBe('Nova Taxa Comum');
        component.speedDialComunsItems[1].command!({} as any);
        expect(component.dialogTitle).toBe('Nova Taxa Extra');
        component.speedDialItems[0].command!({} as any);
        expect(component.dialogTitle).toBe('Nova Taxa Individual');
        component.speedDialItems[1].command!({} as any);
        expect(component.dialogTitle).toBe('Novo Desconto');
        component.speedDialItems[2].command!({} as any);
        expect(component.displayDialogRenegociacao).toBeTrue();
        expect(component.isEdit).toBeFalse();
    });

    it('trata erro do backend ao processar taxas e cobre cores de exibição', async () => {
        const buscar = jasmine.createSpy().and.resolveTo({ status: 'error', message: 'indisponível' });
        (window as any).pywebview = { api: { get_taxas: buscar } };
        component.loadTaxasComuns();
        await Promise.resolve();
        expect(component.taxasComuns).toEqual([]);
        expect(component.loadingComuns).toBeFalse();
        component.loadTaxasIndividuais();
        await Promise.resolve();
        expect(component.taxasIndividuais).toEqual([]);
        expect(component.taxasIndividuaisLoaded).toBeTrue();
        expect(component.getTipoAvatarColor('C')).toBe('#3b82f6');
        expect(component.getTipoAvatarColor('E')).toBe('#8b5cf6');
        expect(component.getTipoAvatarColor('I')).toBe('#10b981');
        expect(component.getTipoAvatarColor('D')).toBe('#ef4444');
        expect(component.getTipoAvatarColor('P')).toBe('#f59e0b');
        expect(component.getTipoAvatarColor('R')).toBe('#ec4899');
        expect(component.getTipoAvatarColor('X')).toBe('#64748b');
    });

    it('recupera falhas de rede nas listagens e usa mocks locais sem backend', async () => {
        (window as any).pywebview = { api: {
            get_taxas: jasmine.createSpy().and.rejectWith(new Error('rede'))
        } };
        component.loadTaxasComuns();
        await Promise.resolve();
        await Promise.resolve();
        expect(component.loadingComuns).toBeFalse();
        component.loadTaxasIndividuais();
        await Promise.resolve();
        await Promise.resolve();
        expect(component.taxasIndividuaisLoaded).toBeTrue();
        delete (window as any).pywebview;
        component.loadTaxasComuns();
        expect(component.taxasComuns.length).toBe(1);
        component.loadTaxasIndividuais();
        expect(component.taxasIndividuaisLoaded).toBeTrue();
    });

    it('carrega taxas para desconto e limpa seleção ao trocar apartamento', async () => {
        const buscar = jasmine.createSpy('get_taxas_por_apartamento').and.resolveTo({ status: 'success', data: [
            { id: 5, valor_original: 100, vencimento: '10/01/2025' }
        ] });
        (window as any).pywebview = { api: { get_taxas_por_apartamento: buscar } };
        component.addTaxa('D');
        expect(component.currentTaxa.tipo).toBe('D');
        expect(component.taxasParaDesconto).toEqual([]);
        component.currentTaxa.apartamento = '101';
        component.competenciaDate = new Date(2025, 0, 1);
        component.loadTaxasParaDesconto();
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledWith('101', ['2025-01', '2025-01'], ['C', 'I', 'E', 'P']);
        expect(component.taxasParaDesconto.length).toBe(1);
        expect(component.getSelectedTaxa()).toBeNull();
        component.currentTaxa.taxa_id = 5;
        expect(component.getSelectedTaxa()?.id).toBe(5);
        component.onDescontoChange();
        expect(component.currentTaxa.taxa_id).toBeNull();
        expect(component.taxasParaDesconto).toEqual([]);
        await Promise.resolve();
        expect(buscar).toHaveBeenCalledTimes(2);
    });

    it('redireciona edição de parcela para a renegociação correspondente', () => {
        const editar = spyOn(component, 'editRenegociacao');
        component.editTaxa({ tipo: 'P', renegociacao_id: 42 });
        component.editTaxa({ tipo: 'R', renegociacao_id: 43 });
        expect(editar).toHaveBeenCalledWith(42);
        expect(editar).toHaveBeenCalledWith(43);
    });

    it('valida desconto obrigatório e valores maiores que a taxa vinculada', async () => {
        const inserir = jasmine.createSpy('insert_taxa').and.resolveTo({ status: 'success' });
        (window as any).pywebview = { api: { insert_taxa: inserir } };
        spyOn(component, 'loadTaxasIndividuais');
        component.addTaxa('D');
        component.currentTaxa.apartamento = '101';
        component.apartamentos = ['101'];
        component.competenciaDate = new Date(2025, 0, 1);
        component.vencimentoDate = new Date(2025, 0, 15);
        component.currentTaxa.descricao = 'Desconto';
        component.currentTaxa.valor_original = 20;
        component.saveTaxa();
        expect(inserir).not.toHaveBeenCalled();
        component.currentTaxa.taxa_id = 5;
        component.taxasParaDesconto = [{ id: 5, valor_original: 10, desconto_vista: 0, multa_percentual: 0, juros_mes_percentual: 0 }];
        component.saveTaxa();
        expect(inserir).not.toHaveBeenCalled();
        expect(component.currentTaxa.valor_original).toBe(20);
    });

    it('salva taxa com erro do backend e pelo caminho mock sem pywebview', async () => {
        const inserir = jasmine.createSpy('insert_taxa').and.resolveTo({ status: 'error', message: 'duplicada' });
        (window as any).pywebview = { api: { insert_taxa: inserir } };
        const mensagens = spyOn(fixture.debugElement.injector.get(MessageService), 'add');
        component.addTaxa('C');
        component.competenciaDate = new Date(2025, 0, 1);
        component.vencimentoDate = new Date(2025, 0, 15);
        component.currentTaxa.descricao = 'Comum';
        component.currentTaxa.valor_original = 50;
        component.saveTaxa();
        await Promise.resolve();
        await Promise.resolve();
        expect(inserir).toHaveBeenCalled();
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error', detail: 'duplicada' }));

        delete (window as any).pywebview;
        spyOn(component, 'loadTaxasComuns');
        component.isEdit = false;
        component.currentTaxa.tipo = 'C';
        component.displayDialog = true;
        component.saveTaxa();
        expect(component.displayDialog).toBeFalse();
        expect(component.loadTaxasComuns).toHaveBeenCalled();
    });

    it('bloqueia exclusão de parcelas e trata erro na exclusão', async () => {
        const mensagens = spyOn(fixture.debugElement.injector.get(MessageService), 'add');
        const confirmar = spyOn(fixture.debugElement.injector.get(ConfirmationService), 'confirm');
        component.currentTaxa = { tipo: 'P', id: 9 };
        component.deleteTaxa();
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error' }));
        expect(confirmar).not.toHaveBeenCalled();

        const excluir = jasmine.createSpy('delete_taxa').and.resolveTo({ status: 'error', message: 'bloqueada' });
        (window as any).pywebview = { api: { delete_taxa: excluir } };
        component.currentTaxa = { tipo: 'C', id: 9 };
        confirmar.and.callFake((opcao: any) => { opcao.accept(); return fixture.debugElement.injector.get(ConfirmationService); });
        component.deleteTaxa();
        await Promise.resolve();
        await Promise.resolve();
        expect(excluir).toHaveBeenCalledWith(9);
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error', detail: 'bloqueada' }));
    });

    it('formata cor e rótulo de avatar por competência', () => {
        expect(component.getAvatarColor('')).toBe('#cbd5e1');
        expect(component.getAvatarColor('2025')).toBe('#cbd5e1');
        expect(component.getAvatarColor('2025-01')).toBe('#f87171');
        expect(component.getAvatarColor('2025-12')).toBe('#64748b');
        expect(component.getAvatarLabelMes('')).toBe('');
        expect(component.getAvatarLabelMes('2025')).toBe('');
        expect(component.getAvatarLabelMes('2025-07')).toBe('07');
    });

    it('inicia nova renegociação e valida guards de cálculo de parcelas', () => {
        component.addRenegociacao();
        expect(component.displayDialogRenegociacao).toBeTrue();
        expect(component.isEdit).toBeFalse();
        expect(component.currentRenegociacao).toEqual({ apartamento: null, numero: '' });
        expect(component.quantidadeParcelas).toBe(1);

        component.vencimentoPrimeiraParcelaDate = null;
        component.gerarParcelasRenegociacao();
        expect(component.parcelasGeradas).toEqual([]);
        component.vencimentoPrimeiraParcelaDate = new Date(2026, 10, 20);
        component.taxasOriginaisSelecionadas = [];
        component.gerarParcelasRenegociacao();
        expect(component.parcelasGeradas).toEqual([]);
        component.taxasOriginaisSelecionadas = [{ vencimento: '14/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1 }];
        component.descontosAdicionais = 200;
        component.onTaxasOriginaisChange();
        component.gerarParcelasRenegociacao();
        expect(component.parcelasGeradas).toEqual([]);
        component.descontosAdicionais = 0;
        component.onTaxasOriginaisChange();
        component.gerarParcelasRenegociacao();
        expect(component.parcelasGeradas.length).toBe(1);
    });

    it('protege formulário de renegociação contra entradas incompletas', () => {
        component.dataRenegociacaoDate = null;
        component.onRenegociacaoFormChange();
        component.dataRenegociacaoDate = new Date(2026, 10, 15);
        component.currentRenegociacao = {};
        component.onRenegociacaoFormChange();
        component.currentRenegociacao = { apartamento: '999' };
        component.apartamentos = ['101'];
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), new Date(2026, 10, 1)];
        component.onRenegociacaoFormChange();
        expect(component.taxasOriginaisParaRenegociacao).toEqual([]);
        component.apartamentos = ['999'];
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), null as any];
        component.onRenegociacaoFormChange();
        expect(component.taxasOriginaisParaRenegociacao).toEqual([]);
    });

    it('calcula dias de atraso com entradas inválidas e valor à vista', () => {
        component.dataRenegociacaoDate = null;
        expect(component.getDiasAtraso('14/11/2026')).toBe(0);
        component.dataRenegociacaoDate = new Date(2026, 10, 15);
        expect(component.getDiasAtraso('')).toBe(0);
        expect(component.getDiasAtraso('invalida')).toBe(0);
        expect(component.getDiasAtraso('14/11/2026')).toBe(1);
        const parcela: any = { valor_original: 100, desconto_vista: 15 };
        component.updateValorAVista(parcela);
        expect(parcela.valor_a_vista).toBe(85);
        expect(component.parcelasDescontoSum).toBe(0);
        component.parcelasGeradas = [{ valor_original: 60, desconto_vista: 5 }, { valor_original: 40, desconto_vista: 0 }];
        expect(component.parcelasDescontoSum).toBe(5);
    });

    it('ignora salvamento de renegociação inválida e trata erro do backend', async () => {
        const salvar = jasmine.createSpy('salvar_renegociacao').and.resolveTo({ status: 'error', message: 'conflito' });
        (window as any).pywebview = { api: { salvar_renegociacao: salvar } };
        const mensagens = spyOn(fixture.debugElement.injector.get(MessageService), 'add');
        component.saveRenegociacao();
        expect(salvar).not.toHaveBeenCalled();

        component.currentRenegociacao = { apartamento: '101' };
        component.competenciaRenegociacaoRange = [new Date(2026, 10, 1), new Date(2026, 10, 1)];
        component.taxasOriginaisSelecionadas = [{ id: 1, vencimento: '16/11/2026', valor_original: 100, multa_percentual: 2, juros_mes_percentual: 1 }];
        component.dataRenegociacaoDate = new Date(2026, 10, 15);
        component.onTaxasOriginaisChange();
        component.gerarParcelasRenegociacao();
        component.saveRenegociacao();
        await Promise.resolve();
        await Promise.resolve();
        expect(salvar).toHaveBeenCalled();
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error', detail: 'conflito' }));
    });

    it('protege exclusão de renegociação sem id e trata erro na exclusão', async () => {
        const confirmar = spyOn(fixture.debugElement.injector.get(ConfirmationService), 'confirm');
        component.currentRenegociacao = {};
        component.deleteRenegociacao();
        expect(confirmar).not.toHaveBeenCalled();

        const excluir = jasmine.createSpy('delete_renegociacao').and.resolveTo({ status: 'error', message: 'impedida' });
        (window as any).pywebview = { api: { delete_renegociacao: excluir } };
        component.currentRenegociacao = { id: 9 };
        const mensagens = spyOn(fixture.debugElement.injector.get(MessageService), 'add');
        confirmar.and.callFake((opcao: any) => { opcao.accept(); return fixture.debugElement.injector.get(ConfirmationService); });
        component.deleteRenegociacao();
        await Promise.resolve();
        await Promise.resolve();
        expect(excluir).toHaveBeenCalledWith(9);
        expect(mensagens).toHaveBeenCalledWith(jasmine.objectContaining({ severity: 'error', detail: 'impedida' }));
        expect(component.displayDialogRenegociacao).toBeFalse();
    });
});
