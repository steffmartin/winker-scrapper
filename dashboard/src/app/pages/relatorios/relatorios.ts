import { ChangeDetectorRef, Component, ElementRef, HostListener, OnDestroy, Type, ViewChild } from '@angular/core';
import { NgComponentOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectModule } from 'primeng/select';
import { TooltipModule } from 'primeng/tooltip';
import { SkeletonModule } from 'primeng/skeleton';
import { ToastModule } from 'primeng/toast';
import { ButtonModule } from 'primeng/button';
import { InputGroupModule } from 'primeng/inputgroup';
import { InputGroupAddonModule } from 'primeng/inputgroupaddon';
import { InputTextModule } from 'primeng/inputtext';
import { MessageService } from 'primeng/api';
import type { ExtratoRecebimentosFiltros, ExtratoRecebimentosResultado } from './extrato-recebimentos';
import type { InadimplenciaFiltros, InadimplenciaResultado } from './relatorio-inadimplencia';
import type { ExtratoContaFiltros, ExtratoContaResultado } from './extrato-conta';

@Component({
    selector: 'app-relatorios',
    standalone: true,
    imports: [FormsModule, SelectModule, TooltipModule, SkeletonModule, ToastModule, NgComponentOutlet, ButtonModule, InputGroupModule, InputGroupAddonModule, InputTextModule],
    providers: [MessageService],
    templateUrl: './relatorios.html'
})
export class RelatoriosComponent implements OnDestroy {
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

    termoBusca = '';
    totalOcorrencias = 0;
    indiceAtual = -1;
    ocorrencias: HTMLElement[] = [];
    private debounceBusca: ReturnType<typeof setTimeout> | null = null;
    @ViewChild('campoBusca') campoBuscaRef?: ElementRef<HTMLInputElement>;

    constructor(private cdr: ChangeDetectorRef, private mensagens: MessageService) {}

    async alterarRelatorio() {
        this.limparBusca();
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
        this.limparBusca();
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
        this.limparBusca();
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
            const resposta = await window.pywebview.api.get_relatorio_recebimentos({ tipo: filtros.tipo, apartamentos: filtros.apartamentos, periodo });
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
        this.limparBusca();
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

    @HostListener('window:keydown', ['$event'])
    aoPressionarTeclas(evento: KeyboardEvent) {
        if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === 'f') {
            if (this.extratoGerado || this.inadimplenciaGerada || this.contaGerada) {
                evento.preventDefault();
                this.campoBuscaRef?.nativeElement.focus();
                this.campoBuscaRef?.nativeElement.select();
            }
        }
    }

    aoPressionarEnter(evento: Event) {
        evento.preventDefault();
        if (evento instanceof KeyboardEvent && evento.shiftKey) {
            this.anteriorOcorrencia();
        } else {
            this.proximaOcorrencia();
        }
    }

    aoDigitarBusca() {
        if (this.debounceBusca) {
            clearTimeout(this.debounceBusca);
        }
        this.debounceBusca = setTimeout(() => {
            this.executarBusca();
        }, 150);
    }

    private obterConteudoContainer(): HTMLElement | null {
        return document.getElementById('corpo-relatorio-conteudo');
    }

    limparDestaques() {
        const container = this.obterConteudoContainer();
        if (container) {
            const marks = container.querySelectorAll('mark.relatorio-busca-termo');
            marks.forEach(mark => {
                const parent = mark.parentNode;
                if (parent) {
                    while (mark.firstChild) {
                        parent.insertBefore(mark.firstChild, mark);
                    }
                    parent.removeChild(mark);
                    parent.normalize();
                }
            });
        }
        this.ocorrencias = [];
        this.totalOcorrencias = 0;
        this.indiceAtual = -1;
    }

    limparBusca() {
        this.termoBusca = '';
        if (this.debounceBusca) {
            clearTimeout(this.debounceBusca);
            this.debounceBusca = null;
        }
        this.limparDestaques();
        this.cdr.markForCheck();
    }

    executarBusca() {
        this.limparDestaques();
        const termo = this.termoBusca.trim();
        if (!termo) {
            this.cdr.markForCheck();
            return;
        }

        const container = this.obterConteudoContainer();
        if (!container) return;

        const regex = this.criarRegexBusca(termo);

        const walker = document.createTreeWalker(
            container,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    const tag = parent.tagName.toLowerCase();
                    if (['script', 'style', 'input', 'textarea', 'button'].includes(tag)) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (parent.closest('.relatorio-acoes, .relatorios-controles, p-toast, button')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (!node.nodeValue?.trim()) {
                        return NodeFilter.FILTER_SKIP;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        const textNodes: Text[] = [];
        let currentNode = walker.nextNode();
        while (currentNode) {
            textNodes.push(currentNode as Text);
            currentNode = walker.nextNode();
        }

        const matches: HTMLElement[] = [];
        for (const node of textNodes) {
            const text = node.nodeValue;
            if (!text) continue;
            regex.lastIndex = 0;
            let match = regex.exec(text);
            if (!match) continue;

            const parent = node.parentNode;
            if (!parent) continue;

            const fragment = document.createDocumentFragment();
            let lastIdx = 0;
            while (match) {
                const matchIdx = match.index;
                const matchLen = match[0].length;

                if (matchIdx > lastIdx) {
                    fragment.appendChild(document.createTextNode(text.substring(lastIdx, matchIdx)));
                }

                const mark = document.createElement('mark');
                mark.className = 'relatorio-busca-termo';
                mark.textContent = text.substring(matchIdx, matchIdx + matchLen);
                fragment.appendChild(mark);
                matches.push(mark);

                lastIdx = matchIdx + matchLen;
                match = regex.exec(text);
            }

            if (lastIdx < text.length) {
                fragment.appendChild(document.createTextNode(text.substring(lastIdx)));
            }

            parent.replaceChild(fragment, node);
        }

        this.ocorrencias = matches;
        this.totalOcorrencias = matches.length;
        if (this.totalOcorrencias > 0) {
            this.indiceAtual = 0;
            matches[0].classList.add('relatorio-busca-ativo');
            matches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
            this.indiceAtual = -1;
        }
        this.cdr.markForCheck();
    }

    proximaOcorrencia() {
        if (this.totalOcorrencias <= 0) return;
        this.ocorrencias[this.indiceAtual]?.classList.remove('relatorio-busca-ativo');
        this.indiceAtual = (this.indiceAtual + 1) % this.totalOcorrencias;
        const ativo = this.ocorrencias[this.indiceAtual];
        if (ativo) {
            ativo.classList.add('relatorio-busca-ativo');
            ativo.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        this.cdr.markForCheck();
    }

    anteriorOcorrencia() {
        if (this.totalOcorrencias <= 0) return;
        this.ocorrencias[this.indiceAtual]?.classList.remove('relatorio-busca-ativo');
        this.indiceAtual = (this.indiceAtual - 1 + this.totalOcorrencias) % this.totalOcorrencias;
        const ativo = this.ocorrencias[this.indiceAtual];
        if (ativo) {
            ativo.classList.add('relatorio-busca-ativo');
            ativo.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        this.cdr.markForCheck();
    }

    private criarRegexBusca(termo: string): RegExp {
        const mapaAcentos: { [key: string]: string } = {
            'a': '[aáàãâäAÁÀÃÂÄ]', 'á': '[aáàãâäAÁÀÃÂÄ]', 'à': '[aáàãâäAÁÀÃÂÄ]', 'ã': '[aáàãâäAÁÀÃÂÄ]', 'â': '[aáàãâäAÁÀÃÂÄ]',
            'e': '[eéèêëEÉÈÊË]', 'é': '[eéèêëEÉÈÊË]', 'ê': '[eéèêëEÉÈÊË]',
            'i': '[iíìîïIÍÌÎÏ]', 'í': '[iíìîïIÍÌÎÏ]',
            'o': '[oóòõôöOÓÒÕÔÖ]', 'ó': '[oóòõôöOÓÒÕÔÖ]', 'õ': '[oóòõôöOÓÒÕÔÖ]', 'ô': '[oóòõôöOÓÒÕÔÖ]',
            'u': '[uúùûüUÚÙÛÜ]', 'ú': '[uúùûüUÚÙÛÜ]',
            'c': '[cçCÇ]', 'ç': '[cçCÇ]'
        };
        let padrao = '';
        for (const char of termo) {
            const c = char.toLowerCase();
            if (mapaAcentos[c]) {
                padrao += mapaAcentos[c];
            } else {
                padrao += char.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            }
        }
        return new RegExp(padrao, 'gi');
    }

    ngOnDestroy() {
        if (this.debounceBusca) {
            clearTimeout(this.debounceBusca);
        }
        this.limparDestaques();
    }
}
