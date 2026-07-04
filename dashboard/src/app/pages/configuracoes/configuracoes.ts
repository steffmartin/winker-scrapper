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
                telefone_administradora: [''],
                saldo_inicial: [0],
                prazo_fechamento: [0, Validators.min(0)],
                inadimplencia_data_corte: [null],
                inadimplencia_unidades: [0],
                inadimplencia_valor: [0]
            }),
            membros: this.fb.array([])
        });

        this.novoMembroForm = this.fb.group({
            nome: ['', Validators.required],
            cargo: ['', Validators.required]
        });
    }

    get membros() {
        return this.configForm.get('membros') as FormArray;
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
                    
                    if (condo.inadimplencia_data_corte && typeof condo.inadimplencia_data_corte === 'string') {
                        const parts = condo.inadimplencia_data_corte.split('/');
                        if (parts.length === 3) {
                            condo.inadimplencia_data_corte = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
                        }
                    }
                    
                    this.configForm.get('condominio')?.patchValue(condo);
                    
                    this.membros.clear();
                    membrosData.forEach((m: any) => {
                        this.membros.push(this.fb.group({
                            nome: [m.nome, Validators.required],
                            cargo: [m.cargo, Validators.required]
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
