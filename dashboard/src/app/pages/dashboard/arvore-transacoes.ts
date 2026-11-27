import { TreeNode } from 'primeng/api';

/** Prepara e filtra a árvore apresentada no dashboard. */
export function processarArvore(nodes: TreeNode[], parentGrupo: string = ''): TreeNode[] {
        return nodes.map(node => {
            let grupo = parentGrupo;
            if (node.data.tipo_node === 'tipo') {
                grupo = node.data.descricao; // 'Receitas' ou 'Despesas'
            }
            node.data.grupo = grupo;

            if (node.children) {
                node.children = processarArvore(node.children, grupo);
            }
            return node;
        });
    }


export function filtrarArvore(nodes: TreeNode[], termo: string): TreeNode[] {
        const apartamentoNumerico = /^\d+$/.test(termo);
        const normalizarNumero = (valor: unknown) => String(valor ?? '').trim().replace(/^0+(?=\d)/, '');
        const normalizarTexto = (valor: unknown) => String(valor ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
        const busca = normalizarTexto(termo);
        const filtrar = (node: TreeNode, grupoCorrespondente = false): TreeNode | null => {
            const dados = node.data;
            if (dados.tipo_node === 'transacao') {
                const corresponde = apartamentoNumerico
                    ? normalizarNumero(dados.apartamento) === normalizarNumero(termo)
                    : grupoCorrespondente || [dados.descricao, dados.data, dados.apartamento, dados.valor].some(v => normalizarTexto(v).includes(busca));
                return corresponde ? { ...node, data: { ...dados } } : null;
            }
            const grupo = grupoCorrespondente || (!apartamentoNumerico && normalizarTexto(dados.descricao).includes(busca));
            const children = (node.children ?? []).map(filho => filtrar(filho, grupo)).filter((n): n is TreeNode => n !== null);
            if (!children.length) return null;
            const valor = (n: TreeNode) => Number((n.data.tipo_node === 'transacao' ? n.data.valor : n.data.valor_total) ?? 0);
            const total = children.reduce((soma, n) => soma + valor(n), 0);
            children.forEach(n => { n.data.porcentagem = total ? 100 * valor(n) / total : 0; });
            return { ...node, expanded: true, data: { ...dados, valor_total: total }, children };
        };
        return nodes.map(node => filtrar(node)).filter((n): n is TreeNode => n !== null);
}
