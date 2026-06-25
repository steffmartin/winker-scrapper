import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [
        CommonModule
    ],
    templateUrl: './dashboard.html'
})
export class Dashboard implements OnInit {
    isMockMode = false;

    ngOnInit() {
        this.detectEnvironmentAndLoad();
    }

    detectEnvironmentAndLoad() {
        const pywebview = (window as any).pywebview;
        if (pywebview && pywebview.api) {
            this.isMockMode = false;
        } else {
            setTimeout(() => {
                const pywebviewRetry = (window as any).pywebview;
                if (pywebviewRetry && pywebviewRetry.api) {
                    this.isMockMode = false;
                } else {
                    console.warn('API pywebview não detectada. Entrando em Modo Simulação (Mocks).');
                    this.isMockMode = true;
                }
            }, 500);
        }
    }
}
