import { CommonModule } from '@angular/common';
import { afterEveryRender, Component, ElementRef, inject, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputGroupModule } from 'primeng/inputgroup';
import { SelectModule } from 'primeng/select';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { DatePickerModule } from 'primeng/datepicker';
import { ImportacaoService } from './importacao.service';

@Component({
    selector: 'app-importacao', standalone: true,
    imports: [CommonModule, FormsModule, ReactiveFormsModule, ButtonModule, InputTextModule, InputGroupModule, SelectModule, ToggleSwitchModule, DatePickerModule],
    templateUrl: './importacao.html',
    styles: [`
        :host { display: flex; flex-direction: column; min-height: calc(100vh - 8rem); }
        .console-card { flex: 1 0 auto; display: flex; flex-direction: column; }
        .console-log { flex: 1 0 20rem; min-height: 20rem; }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown { background-color: var(--p-primary-color); color: var(--p-primary-contrast-color); border-color: var(--p-primary-color); }
    `]
})
export class ImportacaoComponent implements OnInit, OnDestroy {
    @ViewChild('console') console?: ElementRef<HTMLElement>;
    private tamanhoLog = 0;
    private acompanharFinal = true;
    private fb = inject(FormBuilder);
    readonly acompanhamento = inject(ImportacaoService);
    arquivos: string[] = [];
    arquivo = '';
    condominioId: any = null;
    erro = '';
    entrada = '';
    carregado = false;
    iniciando = false;
    niveis = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
    form = this.fb.nonNullable.group({
        user: ['', Validators.required], password: ['', Validators.required], wl: [''],
        portal_index: [1, [Validators.required, Validators.min(1)]], log_level: ['INFO', Validators.required],
        periodo: this.fb.control<(Date | null)[] | null>(null), headless: [true], no_wait: [true]
    });
    private aoConectar = () => void this.listar();

    constructor() { afterEveryRender(() => this.atualizarRolagem()); }

    ngOnInit() { window.addEventListener('pywebviewready', this.aoConectar); void this.listar(); }
    ngOnDestroy() { window.removeEventListener('pywebviewready', this.aoConectar); }
    atualizarRolagem() {
        const tamanho = this.acompanhamento.log().length;
        if (this.console && tamanho !== this.tamanhoLog) {
            if (this.acompanharFinal) this.console.nativeElement.scrollTop = this.console.nativeElement.scrollHeight;
            this.tamanhoLog = tamanho;
        }
    }
    aoRolarConsole() {
        if (!this.console) return;
        const elemento = this.console.nativeElement;
        this.acompanharFinal = elemento.scrollHeight - elemento.scrollTop - elemento.clientHeight <= 2;
    }
    async listar() {
        const api = (window as any).pywebview?.api;
        if (!api?.listar_configs_importacao) return;
        try {
            const resposta = await api.listar_configs_importacao();
            if (resposta.status === 'success') {
                this.arquivos = resposta.data;
                if (resposta.selecionado) { this.arquivo = resposta.selecionado; await this.carregar(); }
            }
            else this.erro = resposta.message;
        } catch { this.erro = 'Não foi possível listar os arquivos de configuração.'; }
    }
    async carregar() {
        this.carregado = false;
        this.erro = '';
        if (!this.arquivo) return;
        try {
            const resposta = await (window as any).pywebview.api.carregar_config_importacao(this.arquivo);
            if (resposta.status !== 'success') { this.erro = resposta.message; return; }
            const { periodo, ...dados } = resposta.data;
            this.form.patchValue({ ...dados, periodo: periodo ? periodo.map((valor: string | null) => this.lerCompetencia(valor)) : null });
            this.condominioId = resposta.condominio_id;
            this.carregado = true;
        } catch { this.erro = 'Não foi possível carregar a configuração.'; }
    }
    async iniciar() {
        if (this.form.invalid || !this.carregado || this.iniciando) return;
        this.iniciando = true;
        this.erro = '';
        try {
            const dados = this.form.getRawValue();
            if (dados.periodo && (!dados.periodo[0] || !dados.periodo[1])) {
                this.erro = 'Selecione o início e o fim do período ou limpe o campo.';
                return;
            }
            const resposta = await (window as any).pywebview.api.iniciar_importacao(this.arquivo, { ...dados, periodo: dados.periodo ? dados.periodo.map(data => this.formatarCompetencia(data)) : null }, this.condominioId);
            if (resposta.status !== 'success') { this.erro = resposta.message; return; }
            this.acompanhamento.reiniciarLog();
            await this.acompanhamento.atualizar();
        } catch { this.erro = 'Não foi possível iniciar a importação.'; }
        finally { this.iniciando = false; }
    }
    async enviar() {
        try {
            const resposta = await (window as any).pywebview.api.enviar_entrada_importacao(this.entrada);
            if (resposta.status === 'success') this.entrada = '';
            else this.erro = resposta.message;
        } catch { this.erro = 'Não foi possível enviar a entrada.'; }
    }
    private lerCompetencia(valor: string | null): Date | null {
        if (!valor || !/^\d{4}-(0[1-9]|1[0-2])$/.test(valor)) return null;
        const [ano, mes] = valor.split('-').map(Number);
        return new Date(ano, mes - 1, 1);
    }
    private formatarCompetencia(data: Date | null): string | null {
        return data ? `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}` : null;
    }
}
