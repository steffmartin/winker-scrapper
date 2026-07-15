import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { DynamicDialogRef, DynamicDialogConfig } from 'primeng/dynamicdialog';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { DatePickerModule } from 'primeng/datepicker';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { TooltipModule } from 'primeng/tooltip';
import { SelectModule } from 'primeng/select';
import { ConfirmationService, MessageService } from 'primeng/api';

@Component({
    selector: 'app-dialog-edicao',
    standalone: true,
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown {
            background-color: var(--p-primary-color) !important;
            border-color: var(--p-primary-color) !important;
            color: var(--p-primary-contrast-color) !important;
        }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown:hover {
            background-color: var(--p-primary-600) !important;
            border-color: var(--p-primary-600) !important;
        }
    `],
    imports: [
        CommonModule, ReactiveFormsModule, InputTextModule, InputNumberModule,
        DatePickerModule, ToggleSwitchModule, ButtonModule, ChipModule, TooltipModule, SelectModule
    ],
    templateUrl: './dialog-edicao.html'
})
export class DialogEdicaoComponent implements OnInit {
    form!: FormGroup;
    registro: any;
    tipo_tabela: string = '';
    motivos: string[] = [];
    canUpload: boolean = true;
    contasList: string[] = [];
    
    documentos: any[] = [];
    saving = false;
    
    constructor(
        public ref: DynamicDialogRef,
        public config: DynamicDialogConfig,
        private fb: FormBuilder,
        private cdr: ChangeDetectorRef,
        private confirmationService: ConfirmationService,
        private messageService: MessageService
    ) {
        this.registro = this.config.data?.registro;
        this.tipo_tabela = this.config.data?.tipo_tabela;
    }

    ngOnInit() {
        try {
            this.motivos = JSON.parse(this.registro.motivo_inconsistencia || '[]');
        } catch(e) {}
        this.buildForm();
        
        if (this.tipo_tabela === 'lancamentos') {
            const pywebview = (window as any).pywebview;
            if (pywebview && pywebview.api) {
                pywebview.api.get_condominio_config().then((res: any) => {
                    if (res.status === 'success' && res.data.contas) {
                        this.contasList = res.data.contas.map((c: any) => c.conta);
                        this.cdr.detectChanges();
                    }
                });
            } else {
                // Mock
                if (window.location.hostname === 'localhost') {
                    this.contasList = ['CONTA CORRENTE', 'POUPANÇA', 'FUNDO DE RESERVA'];
                }
            }
        }
    }

    buildForm() {
        this.form = this.fb.group({
            revisado_usuario: [this.registro.revisado_usuario === 1]
        });

        if (this.tipo_tabela === 'meses') {
            const h_rec = this.motivos.includes("Divergência em receitas") || this.motivos.includes("Divergência em receitas ou despesas");
            const h_des = this.motivos.includes("Divergência em despesas") || this.motivos.includes("Divergência em receitas ou despesas");
            this.canUpload = this.motivos.includes("Mês sem prestação de contas") || this.motivos.includes("Mês sem comprovantes"); // fallback string just in case
            
            this.form.addControl('receita_total', this.fb.control({ value: this.registro.receita_total, disabled: !h_rec }));
            this.form.addControl('despesa_total', this.fb.control({ value: this.registro.despesa_total, disabled: !h_des }));
            this.documentos = this.registro.prestacoes_contas ? [...this.registro.prestacoes_contas] : [];
        } else if (this.tipo_tabela === 'categorias' || this.tipo_tabela === 'subcategorias') {
            const h_val = this.motivos.some(m => m.includes("Soma das subcategorias") || m.includes("Soma das transações"));
            this.form.addControl('valor', this.fb.control({ value: this.registro.valor, disabled: !h_val }));
        } else if (this.tipo_tabela === 'lancamentos') {
            const m = this.motivos;
            const t_inconsistentes = m.includes("Dados da transação inconsistentes");
            
            const h_apt = t_inconsistentes || m.includes("Apartamento não identificado");
            const h_comp = t_inconsistentes || m.includes("Competência não identificada");
            const h_forn = t_inconsistentes || m.includes("Fornecedor não identificado");
            const h_conta = t_inconsistentes || m.includes("Conta não identificada");
            this.canUpload = t_inconsistentes || m.includes("Despesa sem comprovantes") || m.includes("Quantidade de anexos divergente");

            this.form.addControl('apartamento', this.fb.control({ value: this.registro.apartamento, disabled: !h_apt }));
            
            let compDate = null;
            if (this.registro.competencia) {
                const parts = this.registro.competencia.split('-');
                if (parts.length >= 2) {
                    compDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
                }
            }
            this.form.addControl('competencia', this.fb.control({ value: compDate, disabled: !h_comp }));
            this.form.addControl('fornecedor', this.fb.control({ value: this.registro.fornecedor, disabled: !h_forn }));
            this.form.addControl('conta', this.fb.control({ value: this.registro.conta, disabled: !h_conta }));
            this.documentos = this.registro.anexos_lista ? [...this.registro.anexos_lista] : [];
        } else if (this.tipo_tabela === 'documentos') {
            this.canUpload = false;
            const h_ext = this.motivos.includes("Extensão de arquivo inválida ou ausente");
            this.form.addControl('extensao', this.fb.control({ value: this.registro.extensao, disabled: !h_ext }));
        }
    }

    get fieldsToCheck() {
        if (this.tipo_tabela === 'meses') return ['receita_total', 'despesa_total'];
        if (this.tipo_tabela === 'categorias' || this.tipo_tabela === 'subcategorias') return ['valor'];
        if (this.tipo_tabela === 'lancamentos') return ['apartamento', 'competencia', 'fornecedor', 'conta'];
        if (this.tipo_tabela === 'documentos') return ['extensao'];
        return [];
    }

    anexos_removidos_ids: number[] = [];

    addDocumento() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.selecionar_arquivo().then((res: any) => {
                if (res.status === 'success' && res.data) {
                    const path = res.data;
                    const nome = path.split('\\').pop().split('/').pop();
                    this.documentos.push({
                        caminho_local: path,
                        nome_original: nome,
                        isNew: true
                    });
                    this.cdr.detectChanges();
                } else if (res.status === 'error') {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            });
        } else {
            // Mock
            this.documentos.push({
                caminho_local: 'C:\\fakepath\\documento_teste.pdf',
                nome_original: 'documento_teste.pdf',
                isNew: true
            });
        }
    }

    removerDocumento(index: number) {
        if (this.canUpload) {
            if (!this.documentos[index].isNew) {
                this.anexos_removidos_ids.push(this.documentos[index].id);
            }
            this.documentos.splice(index, 1);
            this.form.markAsDirty();
        }
    }

    salvar() {
        const rawValues = this.form.getRawValue();
        this.doSave(rawValues);
    }

    doSave(rawValues: any) {
        this.saving = true;
        let payload: any = { id: this.registro.id, revisado_usuario: rawValues.revisado_usuario ? 1 : 0 };
        
        for (const field of this.fieldsToCheck) {
            if (!this.form.get(field)?.disabled) {
                if (field === 'competencia' && rawValues[field]) {
                    const d = rawValues[field];
                    const month = String(d.getMonth() + 1).padStart(2, '0');
                    payload[field] = `${d.getFullYear()}-${month}`;
                } else {
                    payload[field] = rawValues[field];
                }
            }
        }
        
        if (this.tipo_tabela === 'meses') {
            payload.prestacoes_contas = this.documentos.filter(d => d.isNew);
            payload.anexos_removidos = this.anexos_removidos_ids;
        } else if (this.tipo_tabela === 'lancamentos') {
            payload.anexos_lista = this.documentos.filter(d => d.isNew);
            payload.anexos_removidos = this.anexos_removidos_ids;
        } else if (this.tipo_tabela === 'documentos') {
            payload.tipo_doc = this.registro.tipo_doc;
        }

        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.update_registro_revisado(this.tipo_tabela, payload).then((res: any) => {
                this.saving = false;
                if (res.status === 'success') {
                    this.ref.close({ status: 'success', message: res.message, revisado: payload.revisado_usuario ? 1 : 0, payload: payload });
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
                this.cdr.detectChanges();
            });
        } else {
            // Mock
            setTimeout(() => {
                this.saving = false;
                this.ref.close({ status: 'success', message: 'Registro salvo com sucesso (Mock).', revisado: payload.revisado_usuario ? 1 : 0, payload: payload });
            }, 500);
        }
    }

    cancelar() {
        this.ref.close();
    }
}
