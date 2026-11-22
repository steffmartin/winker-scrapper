import { ChangeDetectorRef, Component, Type } from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectModule } from 'primeng/select';
import { TooltipModule } from 'primeng/tooltip';
import { SkeletonModule } from 'primeng/skeleton';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import type { ExtratoRecebimentosFiltros, ExtratoRecebimentosResultado } from './extrato-recebimentos';
import type { InadimplenciaFiltros, InadimplenciaResultado } from './relatorio-inadimplencia';
import type { ExtratoContaFiltros, ExtratoContaResultado } from './extrato-conta';

@Component({
    selector: 'app-relatorios',
    standalone: true,
    imports: [FormsModule, SelectModule, TooltipModule, SkeletonModule, ToastModule, NgComponentOutlet],
    providers: [MessageService],
    templateUrl: './relatorios.html'
})
export class RelatoriosComponent {
    relatorios = [{ label: 'Extrato de recebimentos', value: 'extrato-recebimentos' }, { label: 'Inadimplência', value: 'inadimplencia' }, { label: 'Extrato de conta', value: 'extrato-conta' }];
    relatorioSelecionado: string | null = null;
    componenteRelatorio: Type<unknown> | null = null;
    readonly aoGerarExtrato = (filtros: ExtratoRecebimentosFiltros) => { void this.gerarExtrato(filtros); };
    readonly aoGerarInadimplencia = (filtros: InadimplenciaFiltros) => { void this.gerarInadimplencia(filtros); };
    readonly aoGerarConta = (filtros: ExtratoContaFiltros) => { void this.gerarConta(filtros); };
    extratoGerado: ExtratoRecebimentosResultado | null = null;
    filtrosGerados: ExtratoRecebimentosFiltros | null = null;
    inadimplenciaGerada: InadimplenciaResultado | null = null;
    filtrosInadimplencia: InadimplenciaFiltros | null = null;
    contaGerada: ExtratoContaResultado | null = null;
    filtrosConta: ExtratoContaFiltros | null = null;
    gerando = false;
    erro = '';
    salvando = false;
    private requisicao = 0;

    constructor(private cdr: ChangeDetectorRef, private mensagens: MessageService) {}

    async alterarRelatorio() {
        this.extratoGerado = null;
        this.filtrosGerados = null;
        this.inadimplenciaGerada = null;
        this.filtrosInadimplencia = null;
        this.contaGerada = null;
        this.filtrosConta = null;
        this.erro = '';
        this.gerando = false;
        this.requisicao++;
        this.componenteRelatorio = null;
        const selecionado = this.relatorioSelecionado;
        try {
            const componente = selecionado === 'extrato-recebimentos'
                ? (await import('./extrato-recebimentos')).ExtratoRecebimentosComponent
                : selecionado === 'inadimplencia'
                    ? (await import('./relatorio-inadimplencia')).RelatorioInadimplenciaComponent
                    : selecionado === 'extrato-conta'
                        ? (await import('./extrato-conta')).ExtratoContaComponent
                    : null;
            if (this.relatorioSelecionado === selecionado) this.componenteRelatorio = componente;
        } catch {
            if (this.relatorioSelecionado === selecionado) this.erro = 'Não foi possível carregar o relatório.';
        }
        this.cdr.markForCheck();
    }

    async gerarConta(filtros: ExtratoContaFiltros) {
        const requisicao = ++this.requisicao;
        this.contaGerada = null;
        this.filtrosConta = null;
        this.erro = '';
        this.gerando = true;
        try {
            const periodo = filtros.periodo?.map(data => data ? `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}` : null) ?? null;
            const resposta = await window.pywebview.api.get_relatorio_conta({ periodo, contas: filtros.contas });
            if (requisicao !== this.requisicao) return;
            if (resposta.status !== 'success') throw new Error(resposta.message || 'Não foi possível gerar o relatório.');
            this.contaGerada = resposta.data;
            this.filtrosConta = { periodo: filtros.periodo?.map(data => data ? new Date(data) : null) ?? null, contas: [...filtros.contas] };
        } catch (erro) {
            if (requisicao !== this.requisicao) return;
            this.erro = erro instanceof Error ? erro.message : 'Não foi possível gerar o relatório.';
        } finally {
            if (requisicao === this.requisicao) { this.gerando = false; this.cdr.markForCheck(); }
        }
    }

    async gerarExtrato(filtros: ExtratoRecebimentosFiltros) {
        const requisicao = ++this.requisicao;
        this.extratoGerado = null;
        this.filtrosGerados = null;
        this.erro = '';
        this.gerando = true;
        try {
            const periodo = filtros.periodo?.map(data => {
                if (!data) return null;
                const ano = data.getFullYear(), mes = String(data.getMonth() + 1).padStart(2, '0');
                return filtros.tipo === 'competencia' ? `${ano}-${mes}` : `${ano}-${mes}-${String(data.getDate()).padStart(2, '0')}`;
            }) ?? null;
            const resposta = await window.pywebview.api.get_relatorio_recebimentos({ ...filtros, periodo });
            if (requisicao !== this.requisicao) return;
            if (resposta.status !== 'success') throw new Error(resposta.message || 'Não foi possível gerar o relatório.');
            this.extratoGerado = resposta.data;
            this.filtrosGerados = { ...filtros, apartamentos: [...filtros.apartamentos], periodo: filtros.periodo?.map(data => data ? new Date(data) : null) ?? null };
        } catch (erro) {
            if (requisicao !== this.requisicao) return;
            this.erro = erro instanceof Error ? erro.message : 'Não foi possível gerar o relatório.';
        } finally {
            if (requisicao === this.requisicao) {
                this.gerando = false;
                this.cdr.markForCheck();
            }
        }
    }

    async gerarInadimplencia(filtros: InadimplenciaFiltros) {
        const requisicao = ++this.requisicao;
        this.inadimplenciaGerada = null;
        this.filtrosInadimplencia = null;
        this.erro = '';
        this.gerando = true;
        try {
            const data = filtros.data_corte;
            const data_corte = data ? `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}` : null;
            const resposta = await window.pywebview.api.get_relatorio_inadimplencia({ data_corte, apartamentos: filtros.apartamentos });
            if (requisicao !== this.requisicao) return;
            if (resposta.status !== 'success') throw new Error(resposta.message || 'Não foi possível gerar o relatório.');
            this.inadimplenciaGerada = resposta.data;
            this.filtrosInadimplencia = { data_corte: data ? new Date(data) : null, apartamentos: [...filtros.apartamentos] };
        } catch (erro) {
            if (requisicao !== this.requisicao) return;
            this.erro = erro instanceof Error ? erro.message : 'Não foi possível gerar o relatório.';
        } finally {
            if (requisicao === this.requisicao) { this.gerando = false; this.cdr.markForCheck(); }
        }
    }

    imprimir() {
        window.print();
    }

    async salvar() {
        if (this.salvando) return;
        this.salvando = true;
        try {
            const titulo = document.getElementById('titulo-relatorio')?.textContent?.trim() || 'Relatório';
            const resposta = await window.pywebview.api.salvar_relatorio_pdf(titulo);
            if (resposta.status === 'success') this.mensagens.add({ severity: 'success', summary: 'Sucesso', detail: 'PDF salvo com sucesso.' });
            else if (resposta.status !== 'cancelled') throw new Error(resposta.message || 'Não foi possível salvar o PDF.');
        } catch (erro) {
            this.mensagens.add({ severity: 'error', summary: 'Erro ao salvar', detail: erro instanceof Error ? erro.message : 'Não foi possível salvar o PDF.' });
        } finally {
            this.salvando = false;
            this.cdr.markForCheck();
        }
    }
}
