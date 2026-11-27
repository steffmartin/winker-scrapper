import { Injectable, signal } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ImportacaoService {
    estado = signal<any>({ is_running: false, resultado: null, erro: null });
    log = signal('');
    readonly concluida = new Subject<void>();
    private ultimaConclusao: number | null = null;
    private cursor = 0;
    private consultando = false;

    constructor() {
        window.addEventListener('pywebviewready', () => void this.atualizar());
        setInterval(() => void this.atualizar(), 1000);
        void this.atualizar();
    }

    async atualizar() {
        const api = (window as any).pywebview?.api;
        if (!api?.obter_estado_importacao || this.consultando) return;
        this.consultando = true;
        try {
            const resposta = await api.obter_estado_importacao(this.cursor);
            if (resposta.status === 'success') {
                const dados = resposta.data;
                if (dados.cursor < this.cursor) this.log.set('');
                this.log.update(valor => valor + dados.log);
                this.cursor = dados.cursor;
                this.estado.set(dados);
                if (!dados.is_running && dados.resultado && dados.id != null && dados.id !== this.ultimaConclusao) {
                    this.ultimaConclusao = dados.id;
                    this.concluida.next();
                }
            }
        } catch {
            // A conexão pode ainda não estar pronta; a próxima consulta tentará novamente.
        } finally { this.consultando = false; }
    }

    reiniciarLog() { this.cursor = 0; this.log.set(''); }
}
