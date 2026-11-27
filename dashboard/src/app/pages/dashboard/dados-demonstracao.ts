import { TreeNode } from 'primeng/api';

/** Dados de demonstração usados quando o desktop não está disponível. */
export function criarKpisDemonstracao(): any {
    return {
            inadimplencia: {
                valor: 2500.50,
                unidades: 3,
                data_corte: '2023-10-01'
            },
            gestao: {
                membros: [
                    { nome: 'Carlos Silva', cargo: 'Síndico' },
                    { nome: 'Ana Souza', cargo: 'Conselheiro' },
                    { nome: 'Pedro Álvares', cargo: 'Advogado' },
                    { nome: 'Maria Lima', cargo: 'Conselheiro' },
                    { nome: 'João Ferreira', cargo: 'Conselheiro' },
                    { nome: 'Paulo César', cargo: 'Subsíndico' }
                ],
                administradora: {
                    nome: 'Admin Teste LTDA',
                    telefone: '(11) 9999-9999'
                }
            },
            saldos: {
                saldo_total: 0,
                saldo_declarado: 0,
                contas: [
                    { nome: 'Conta Corrente Padrão', saldo: 0 },
                    { nome: 'Fundo de Reserva', saldo: 0 }
                ]
            },
            resumo_mes: {
                competencia: '10/2023',
                receita_total: 30000.00,
                despesa_total: 28000.00,
                resultado: 2000.00
            }
        };
}

export function criarTransacoesDemonstracao(): TreeNode[] {
    return [
                {
                    data: { descricao: 'Junho/2026', valor_total: 3500, tipo_node: 'mes' },
                    expanded: true,
                    children: [
                        {
                            data: { descricao: 'Receitas', valor_total: 2000, porcentagem: 57.14, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Taxa Condominial', valor_total: 2000, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: true,
                                    children: [
                                        {
                                            data: { descricao: 'Cotas Ordinárias', valor_total: 2000, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                            expanded: true,
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Boleto',
                                                        fornecedor: '-',
                                                        apartamento: '101',
                                                        competencia: '06/2026',
                                                        valor: 1200,
                                                        data: '2026-06-05',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 1
                                                    }
                                                },
                                                {
                                                    data: {
                                                        descricao: 'Boleto',
                                                        fornecedor: '-',
                                                        apartamento: '102',
                                                        competencia: '06/2026',
                                                        valor: 800,
                                                        data: '2026-06-07',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 0
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            data: { descricao: 'Despesas', valor_total: 1500, porcentagem: 42.86, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Despesas Ordinárias', valor_total: 1500, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: true,
                                    children: [
                                        {
                                            data: { descricao: 'Limpeza', valor_total: 1500, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                    expanded: true,
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Compra de produtos',
                                                        fornecedor: 'Mercado X',
                                                        apartamento: 'Condomínio',
                                                        competencia: '06/2026',
                                                        valor: 1500,
                                                        data: '2026-06-15',
                                                        revisado: false,
                                                        tipo_node: 'transacao',
                                                        anexos: 2
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    data: { descricao: 'Maio/2026', valor_total: 1000, tipo_node: 'mes' },
                    expanded: false,
                    children: [
                        {
                            data: { descricao: 'Despesas', valor_total: 1000, porcentagem: 100.0, tipo_node: 'tipo' },
                            expanded: true,
                            children: [
                                {
                                    data: { descricao: 'Despesas Ordinárias', valor_total: 1000, porcentagem: 100.0, tipo_node: 'categoria' },
                                    expanded: false,
                                    children: [
                                        {
                                            data: { descricao: 'Manutenção', valor_total: 1000, porcentagem: 100.0, tipo_node: 'subcategoria' },
                                            children: [
                                                {
                                                    data: {
                                                        descricao: 'Conserto Elevador',
                                                        fornecedor: 'Elevadores SA',
                                                        apartamento: '-',
                                                        competencia: '05/2026',
                                                        valor: 1000,
                                                        data: '2026-05-20',
                                                        revisado: true,
                                                        tipo_node: 'transacao',
                                                        anexos: 1
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ];
}
