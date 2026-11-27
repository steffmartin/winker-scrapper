/** Cálculos da simulação de renegociação exibida na tela de cobranças. */
export function calcularDiasAtraso(vencimentoStr: string, dataRenegociacaoDate: Date | null): number {
        if (!vencimentoStr || !dataRenegociacaoDate) return 0;
        const parts = vencimentoStr.split('/');
        if (parts.length !== 3) return 0;
        
        // Ignora a hora para garantir cálculo preciso de dias
        const vencDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
        vencDate.setHours(0, 0, 0, 0);
        
        const renDate = new Date(dataRenegociacaoDate);
        renDate.setHours(0, 0, 0, 0);
        
        const diffTime = renDate.getTime() - vencDate.getTime();
        const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
        return diffDays > 0 ? diffDays : 0;
    }


export function calcularTaxa(t: any, dataRenegociacaoDate: Date | null, tipo_juros_multa: string) {
        const dias = calcularDiasAtraso(t.vencimento, dataRenegociacaoDate);
        const valor = t.valor_original || 0;
        const jurosPerc = t.juros_mes_percentual || 0;
        const multaPerc = dias > 0 ? (t.multa_percentual || 0) : 0;
        let juros = valor * (jurosPerc / 30 / 100) * dias;
        let multa = valor * (multaPerc / 100);
        if (tipo_juros_multa === 'M') multa = (valor + juros) * (multaPerc / 100);
        if (tipo_juros_multa === 'J') juros = (valor + multa) * (jurosPerc / 30 / 100) * dias;
        return { valor, multa, juros, geral: valor + multa + juros };
    }


export function calcularTotalTaxas(taxas: any[], dataRenegociacaoDate: Date | null, tipo_juros_multa: string) {
        const selecionadas = taxas || [];
        const total = { valor: 0, desconto: 0, multa: 0, juros: 0, geral: 0 };
        for (const taxa of selecionadas.filter(t => t.tipo !== 'D')) {
            const original = calcularTaxa(taxa, dataRenegociacaoDate, tipo_juros_multa);
            const liquida = { ...taxa };
            for (const desconto of selecionadas.filter(t => t.tipo === 'D' && t.taxa_id === taxa.id)) {
                for (const campo of ['valor_original', 'multa_percentual', 'juros_mes_percentual']) {
                    liquida[campo] = Math.max(0, (liquida[campo] || 0) - (desconto[campo] || 0));
                }
            }
            const ajustada = calcularTaxa(liquida, dataRenegociacaoDate, tipo_juros_multa);
            total.valor += original.valor;
            total.desconto += original.valor - ajustada.valor;
            total.multa += ajustada.multa;
            total.juros += ajustada.juros;
            total.geral += ajustada.geral;
        }
        return total;
    }

