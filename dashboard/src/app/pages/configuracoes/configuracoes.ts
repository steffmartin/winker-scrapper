import { Component, HostListener, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { CardModule } from 'primeng/card';
import { TabsModule } from 'primeng/tabs';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { InputMaskModule } from 'primeng/inputmask';
import { ButtonModule } from 'primeng/button';
import { ToastModule } from 'primeng/toast';
import { MessageService, ConfirmationService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { ChipModule } from 'primeng/chip';
import { TooltipModule } from 'primeng/tooltip';

@Component({
    selector: 'app-configuracoes',
    standalone: true,
    imports: [
        CommonModule, ReactiveFormsModule, CardModule, TabsModule, 
        InputTextModule, InputNumberModule, InputMaskModule, ButtonModule, ToastModule,
        ConfirmDialogModule, DatePickerModule, DialogModule, ChipModule, TooltipModule
    ],
    providers: [MessageService, ConfirmationService],
    templateUrl: './configuracoes.html',
    styles: [`
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown {
            background-color: var(--p-primary-color, var(--primary-color)) !important;
            border-color: var(--p-primary-color, var(--primary-color)) !important;
            color: var(--p-primary-contrast-color, var(--primary-color-text)) !important;
        }
        :host ::ng-deep .primary-datepicker-btn button.p-datepicker-dropdown:hover {
            background-color: var(--p-primary-hover-color, var(--primary-600)) !important;
            border-color: var(--p-primary-hover-color, var(--primary-600)) !important;
        }
        :host ::ng-deep .primary-inputnumber-btn button.p-inputnumber-button {
            background-color: var(--p-primary-color, var(--primary-color)) !important;
            border-color: var(--p-primary-color, var(--primary-color)) !important;
            color: var(--p-primary-contrast-color, var(--primary-color-text)) !important;
        }
        :host ::ng-deep .primary-inputnumber-btn button.p-inputnumber-button:hover {
            background-color: var(--p-primary-hover-color, var(--primary-600)) !important;
            border-color: var(--p-primary-hover-color, var(--primary-600)) !important;
        }
    `]
})
export class ConfiguracoesComponent implements OnInit {
    configForm: FormGroup;
    loading = false;
    isSaving = false;
    maxDate = new Date();
    displayMembroDialog = false;
    novoMembroForm: FormGroup;
    
    displayTelefoneDialog = false;
    novoTelefoneForm: FormGroup;

    displayContaDialog = false;
    novoContaForm: FormGroup;

    constructor(
        private fb: FormBuilder, 
        private messageService: MessageService, 
        private confirmationService: ConfirmationService,
        private cdr: ChangeDetectorRef
    ) {
        this.configForm = this.fb.group({
            condominio: this.fb.group({
                nome: ['', Validators.required],
                administradora: [''],
                telefone_administradora: this.fb.array([]),
                prazo_fechamento: [0, Validators.min(0)],
                inadimplencia_data_corte: [null],
                inadimplencia_unidades: [0],
                inadimplencia_valor: [0]
            }),
            membros: this.fb.array([]),
            contas: this.fb.array([])
        });

        this.novoMembroForm = this.fb.group({
            nome: ['', Validators.required],
            cargo: ['', Validators.required]
        });

        this.novoTelefoneForm = this.fb.group({
            numero: ['', Validators.required]
        });

        this.novoContaForm = this.fb.group({
            conta: ['', Validators.required],
            saldo_inicial: [0, Validators.required]
        });
    }

    get membros() {
        return this.configForm.get('membros') as FormArray;
    }

    get telefones() {
        return this.configForm.get('condominio.telefone_administradora') as FormArray;
    }

    get contas() {
        return this.configForm.get('contas') as FormArray;
    }

    ngOnInit() {
        this.loadData();
    }

    @HostListener('window:beforeunload', ['$event'])
    unloadNotification($event: any) {
        if (!this.isSaving && this.configForm.dirty) {
            $event.returnValue = true;
        }
    }

    canDeactivate(): Promise<boolean> | boolean {
        if (!this.isSaving && this.configForm.dirty) {
            return new Promise((resolve) => {
                this.confirmationService.confirm({
                    message: 'Você tem alterações não salvas. Deseja realmente sair sem salvar?',
                    header: 'Atenção',
                    icon: 'pi pi-exclamation-triangle',
                    acceptLabel: 'Sair',
                    rejectLabel: 'Voltar',
                    acceptButtonStyleClass: 'p-button-secondary',
                    accept: () => resolve(true),
                    reject: () => resolve(false)
                });
            });
        }
        return true;
    }

    loadData() {
        this.loading = true;
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.get_condominio_config().then((res: any) => {
                this.loading = false;
                if (res.status === 'success') {
                    const condo = res.data.condominio || {};
                    const membrosData = res.data.membros || [];
                    const contasData = res.data.contas || [];
                    
                    if (condo.inadimplencia_data_corte && typeof condo.inadimplencia_data_corte === 'string') {
                        const parts = condo.inadimplencia_data_corte.split('/');
                        if (parts.length === 3) {
                            condo.inadimplencia_data_corte = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
                        }
                    }
                    
                    const telefonesList = condo.telefone_administradora || [];
                    delete condo.telefone_administradora;

                    this.configForm.get('condominio')?.patchValue(condo);
                    
                    this.telefones.clear();
                    if (Array.isArray(telefonesList)) {
                        telefonesList.forEach((t: string) => {
                            this.telefones.push(this.fb.control(t));
                        });
                    }

                    this.membros.clear();
                    membrosData.forEach((m: any) => {
                        this.membros.push(this.fb.group({
                            nome: [m.nome, Validators.required],
                            cargo: [m.cargo, Validators.required]
                        }));
                    });

                    this.contas.clear();
                    contasData.forEach((c: any) => {
                        this.contas.push(this.fb.group({
                            conta: [c.conta, Validators.required],
                            saldo_inicial: [c.saldo_inicial, Validators.required]
                        }));
                    });
                    
                    this.configForm.markAsPristine();
                    this.cdr.detectChanges();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            }).catch(() => {
                this.loading = false;
            });
        } else {
            this.loading = false;
        }
    }

    showDialog() {
        this.novoMembroForm.reset();
        this.displayMembroDialog = true;
    }

    salvarNovoMembro() {
        if (this.novoMembroForm.valid) {
            this.membros.push(this.fb.group({
                nome: [this.novoMembroForm.value.nome, Validators.required],
                cargo: [this.novoMembroForm.value.cargo, Validators.required]
            }));
            this.configForm.markAsDirty();
            this.displayMembroDialog = false;
        }
    }

    getMembroIcon(cargo: string): string | undefined {
        if (!cargo) return undefined;
        const normalized = cargo.toLowerCase().trim();
        if (normalized === 'síndico' || normalized === 'sindico') {
            return 'pi pi-crown';
        }
        return undefined;
    }

    removeMembro(index: number) {
        this.membros.removeAt(index);
        this.configForm.markAsDirty();
    }

    showTelefoneDialog() {
        this.novoTelefoneForm.reset();
        this.displayTelefoneDialog = true;
    }

    salvarNovoTelefone() {
        if (this.novoTelefoneForm.valid) {
            let numero = this.novoTelefoneForm.value.numero;
            if (numero) {
                numero = numero.replace(/\D/g, '');
                this.telefones.push(this.fb.control(numero));
                this.configForm.markAsDirty();
            }
            this.displayTelefoneDialog = false;
        }
    }

    removeTelefone(index: number) {
        this.telefones.removeAt(index);
        this.configForm.markAsDirty();
    }

    onTelefoneInput(event: any) {
        let val = event.target.value.replace(/\D/g, '');
        if (val.length > 11) val = val.substring(0, 11);
        
        let formatado = '';
        if (val.length === 0) {
            formatado = '';
        } else if (val.length <= 2) {
            formatado = `(${val}`;
        } else if (val.length <= 6) {
            formatado = `(${val.substring(0, 2)}) ${val.substring(2)}`;
        } else if (val.length <= 10) {
            formatado = `(${val.substring(0, 2)}) ${val.substring(2, 6)}-${val.substring(6)}`;
        } else {
            formatado = `(${val.substring(0, 2)}) ${val.substring(2, 7)}-${val.substring(7)}`;
        }
        
        this.novoTelefoneForm.patchValue({ numero: formatado }, { emitEvent: false });
    }

    formatarTelefone(tel: string): string {
        if (!tel) return '';
        const d = tel.replace(/\D/g, '');
        if (d.length === 11) {
            return `(${d.substring(0, 2)}) ${d.substring(2, 7)}-${d.substring(7, 11)}`;
        } else if (d.length === 10) {
            return `(${d.substring(0, 2)}) ${d.substring(2, 6)}-${d.substring(6, 10)}`;
        }
        return tel;
    }

    showContaDialog() {
        this.novoContaForm.reset({ saldo_inicial: 0 });
        this.displayContaDialog = true;
    }

    salvarNovaConta() {
        if (this.novoContaForm.valid) {
            this.contas.push(this.fb.group({
                conta: [this.novoContaForm.value.conta, Validators.required],
                saldo_inicial: [this.novoContaForm.value.saldo_inicial, Validators.required]
            }));
            this.configForm.markAsDirty();
            this.displayContaDialog = false;
        }
    }

    removeConta(index: number) {
        this.contas.removeAt(index);
        this.configForm.markAsDirty();
    }

    formatarContaLabel(conta: any): string {
        if (!conta || !conta.conta) return '';
        const formatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
        const saldoFormatado = formatter.format(conta.saldo_inicial || 0);
        return `${conta.conta} (${saldoFormatado})`;
    }

    salvar() {
        if (this.configForm.invalid) {
            this.messageService.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha os campos obrigatórios corretamente.' });
            return;
        }
        
        this.isSaving = true;
        this.loading = true;
        
        // Clone for payload
        const payload = JSON.parse(JSON.stringify(this.configForm.value));
        const formValues = this.configForm.value;
        const dataCorte = formValues.condominio.inadimplencia_data_corte;
        if (dataCorte instanceof Date) {
            const day = String(dataCorte.getDate()).padStart(2, '0');
            const month = String(dataCorte.getMonth() + 1).padStart(2, '0');
            const year = dataCorte.getFullYear();
            payload.condominio.inadimplencia_data_corte = `${day}/${month}/${year}`;
        }
        
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            pywebview.api.update_condominio_config(payload).then((res: any) => {
                this.loading = false;
                this.isSaving = false;
                if (res.status === 'success') {
                    this.configForm.markAsPristine();
                    this.messageService.add({ severity: 'success', summary: 'Sucesso', detail: res.message });
                    this.cdr.detectChanges();
                } else {
                    this.messageService.add({ severity: 'error', summary: 'Erro', detail: res.message });
                }
            }).catch((err: any) => {
                this.loading = false;
                this.isSaving = false;
                this.messageService.add({ severity: 'error', summary: 'Erro', detail: 'Erro ao salvar configurações.' });
            });
        } else {
            this.loading = false;
            this.isSaving = false;
        }
    }
}
