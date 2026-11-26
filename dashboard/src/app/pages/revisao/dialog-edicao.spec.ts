import { TestBed } from '@angular/core/testing';
import { ConfirmationService, MessageService } from 'primeng/api';
import { DynamicDialogConfig, DynamicDialogRef } from 'primeng/dynamicdialog';
import { DialogEdicaoComponent } from './dialog-edicao';

describe('Edição de registros de revisão', () => {
    const fechar = jasmine.createSpy('close');
    async function criar(tipo: string, registro: any) {
        await TestBed.configureTestingModule({
            imports: [DialogEdicaoComponent],
            providers: [ConfirmationService, MessageService,
                { provide: DynamicDialogRef, useValue: { close: fechar } },
                { provide: DynamicDialogConfig, useValue: { data: { tipo_tabela: tipo, registro } } }]
        }).compileComponents();
        const fixture = TestBed.createComponent(DialogEdicaoComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        return fixture.componentInstance;
    }
    beforeEach(() => fechar.calls.reset());
    afterEach(() => { delete window.pywebview; });

    it('edita apenas campos inconsistentes do mês e envia alterações de documentos', async () => {
        const salvar = jasmine.createSpy().and.resolveTo({ status: 'success', message: 'Salvo' });
        window.pywebview = { api: { update_registro_revisado: salvar } };
        const componente = await criar('meses', { id: 3, revisado_usuario: 0, receita_total: 100, despesa_total: 30,
            motivo_inconsistencia: JSON.stringify(['Divergência em receitas', 'Mês sem prestação de contas']),
            prestacoes_contas: [{ id: 9, nome_original: 'antigo.pdf' }] });
        expect(componente.form.get('receita_total')?.enabled).toBeTrue();
        expect(componente.form.get('despesa_total')?.disabled).toBeTrue();
        componente.removerDocumento(0);
        componente.documentos.push({ isNew: true, caminho_local: 'C:/teste/novo.pdf' });
        componente.form.patchValue({ receita_total: 120, revisado_usuario: true });
        componente.salvar();
        expect(salvar).toHaveBeenCalledWith('meses', jasmine.objectContaining({ id: 3, receita_total: 120,
            revisado_usuario: 1, anexos_removidos: [9], prestacoes_contas: [{ isNew: true, caminho_local: 'C:/teste/novo.pdf' }] }));
        expect(salvar.calls.mostRecent().args[1].despesa_total).toBeUndefined();
        await Promise.resolve();
        expect(fechar).toHaveBeenCalledWith(jasmine.objectContaining({ status: 'success', revisado: 1 }));
    });

    it('valida unidade e converte competência ao revisar lançamento', async () => {
        const salvar = jasmine.createSpy().and.resolveTo({ status: 'success' });
        window.pywebview = { api: { update_registro_revisado: salvar,
            get_condominio_config: () => Promise.resolve({ status: 'success', data: {
                condominio: { apartamentos: ['101'] }, contas: [{ conta: 'Corrente' }]
            } }) } };
        const componente = await criar('lancamentos', { id: 4, revisado_usuario: 0, apartamento: '101',
            competencia: '2025-02', motivo_inconsistencia: JSON.stringify(['Dados da transação inconsistentes']) });
        expect(componente.contasList).toEqual(['Corrente']);
        componente.form.patchValue({ apartamento: '999' });
        componente.salvar();
        expect(salvar).not.toHaveBeenCalled();
        componente.form.patchValue({ apartamento: '101', competencia: new Date(2025, 2, 1), revisado_usuario: true });
        componente.salvar();
        expect(salvar).toHaveBeenCalledWith('lancamentos', jasmine.objectContaining({ apartamento: '101', competencia: '2025-03' }));
        await Promise.resolve();
        expect(fechar).toHaveBeenCalled();
    });

    it('revisa extensão de documento sem permitir envio de outro arquivo', async () => {
        const salvar = jasmine.createSpy().and.resolveTo({ status: 'success' });
        window.pywebview = { api: { update_registro_revisado: salvar } };
        const componente = await criar('documentos', { id: 7, tipo_doc: 'C', revisado_usuario: 0, extensao: '',
            motivo_inconsistencia: JSON.stringify(['Extensão de arquivo inválida ou ausente']) });
        expect(componente.canUpload).toBeFalse();
        componente.form.patchValue({ extensao: 'pdf', revisado_usuario: true });
        componente.salvar();
        expect(salvar).toHaveBeenCalledWith('documentos', { id: 7, tipo_doc: 'C', extensao: 'pdf', revisado_usuario: 1 });
    });

    it('habilita valor de categoria divergente e permite cancelar', async () => {
        const componente = await criar('categorias', { id: 8, valor: 45, revisado_usuario: 0,
            motivo_inconsistencia: JSON.stringify(['Soma das subcategorias divergente']) });
        expect(componente.form.get('valor')?.enabled).toBeTrue();
        expect(componente.fieldsToCheck).toEqual(['valor']);
        componente.cancelar();
        expect(fechar).toHaveBeenCalledOnceWith();
    });

    it('seleciona arquivo e remove novos documentos sem registrar exclusão antiga', async () => {
        const selecionar = jasmine.createSpy().and.resolveTo({ status: 'success', data: 'C:\\teste\\nota.pdf' });
        window.pywebview = { api: { selecionar_arquivo: selecionar } };
        const componente = await criar('meses', { id: 1, revisado_usuario: 0, receita_total: 0, despesa_total: 0,
            motivo_inconsistencia: JSON.stringify(['Mês sem prestação de contas']), prestacoes_contas: [] });
        componente.addDocumento();
        await Promise.resolve();
        expect(componente.documentos[0].nome_original).toBe('nota.pdf');
        componente.removerDocumento(0);
        expect(componente.documentos).toEqual([]);
        expect(componente.anexos_removidos_ids).toEqual([]);
        expect(componente.form.dirty).toBeTrue();
    });
});
