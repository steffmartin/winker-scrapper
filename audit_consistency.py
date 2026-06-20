import sqlite3
import os
import json

def format_motivo(motivo_str):
    if not motivo_str:
        return 'Inconsistência não especificada'
    try:
        reasons = json.loads(motivo_str)
        if isinstance(reasons, list):
            return " | ".join(reasons)
    except Exception:
        pass
    return motivo_str

def check_consistency():
    db_path = "winker_data.db"
    if not os.path.exists(db_path):
        print(f"Banco de dados não encontrado em '{db_path}'")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Identificar meses que possuem inconsistências
    cursor.execute("SELECT id, exibicao, receita_total, despesa_total, motivo_inconsistencia FROM meses WHERE consistente = 0")
    inconsistent_months = cursor.fetchall()
    
    report = []
    report.append("# Relatório Detalhado de Consistência e Auditoria")
    report.append("Este relatório é baseado nos motivos de inconsistência pré-calculados e armazenados no banco de dados no formato JSON.\n")
    
    print(f"Meses inconsistentes encontrados no banco: {len(inconsistent_months)}\n")
    
    # 1. Auditoria de Meses
    if inconsistent_months:
        report.append("## ⚠️ Meses Inconsistentes")
        for m_id, exib, rec_tot, desp_tot, motivo in inconsistent_months:
            motivo_fmt = format_motivo(motivo)
            report.append(f"- **{exib} ({m_id})**: {motivo_fmt}")
            report.append(f"  - Receita Declarada: R$ {rec_tot:,.2f} | Despesa Declarada: R$ {desp_tot:,.2f}")
        report.append("")

    # 2. Auditoria de Categorias
    cursor.execute("""
        SELECT c.nome, c.tipo, c.valor, c.motivo_inconsistencia, m.exibicao
        FROM categorias c
        JOIN meses m ON c.mes_id = m.id
        WHERE c.consistente = 0
    """)
    inconsistent_cats = cursor.fetchall()
    if inconsistent_cats:
        report.append("## ⚠️ Categorias Inconsistentes")
        for nome, tipo, valor, motivo, mes_exib in inconsistent_cats:
            t_str = "Receita" if tipo == 'R' else "Despesa"
            motivo_fmt = format_motivo(motivo)
            report.append(f"- **{mes_exib} > {nome}** ({t_str}): Valor = R$ {valor:,.2f}")
            report.append(f"  - *Motivo*: {motivo_fmt}")
        report.append("")

    # 3. Auditoria de Subcategorias
    cursor.execute("""
        SELECT s.nome, s.tipo, s.valor, s.motivo_inconsistencia, m.exibicao, c.nome
        FROM subcategorias s
        JOIN categorias c ON s.categoria_id = c.id
        JOIN meses m ON c.mes_id = m.id
        WHERE s.consistente = 0
    """)
    inconsistent_subs = cursor.fetchall()
    if inconsistent_subs:
        report.append("## ⚠️ Subcategorias Inconsistentes")
        for nome, tipo, valor, motivo, mes_exib, cat_nome in inconsistent_subs:
            t_str = "Receita" if tipo == 'R' else "Despesa"
            motivo_fmt = format_motivo(motivo)
            report.append(f"- **{mes_exib} > {cat_nome} > {nome}** ({t_str}): Valor = R$ {valor:,.2f}")
            report.append(f"  - *Motivo*: {motivo_fmt}")
        report.append("")

    # 4. Auditoria de Transações
    cursor.execute("""
        SELECT t.id, t.tipo, t.data, t.descricao, t.valor, t.motivo_inconsistencia, s.nome, m.exibicao
        FROM transacoes t
        JOIN subcategorias s ON t.subcategoria_id = s.id
        JOIN categorias c ON s.categoria_id = c.id
        JOIN meses m ON c.mes_id = m.id
        WHERE t.consistente = 0
    """)
    inconsistent_trans = cursor.fetchall()
    if inconsistent_trans:
        report.append("## ⚠️ Transações Inconsistentes")
        for t_id, tipo, data_t, desc, val, motivo, sub_nome, mes_exib in inconsistent_trans:
            t_str = "Receita" if tipo == 'R' else "Despesa"
            motivo_fmt = format_motivo(motivo)
            report.append(f"- **{mes_exib} > {sub_nome} > {desc}** ({data_t or 'S/D'}) - R$ {val:,.2f}")
            report.append(f"  - *Motivo*: {motivo_fmt}")
        report.append("")

    # 5. Auditoria de Anexos
    cursor.execute("""
        SELECT a.nome_original, a.caminho_local, a.motivo_inconsistencia, t.descricao, m.exibicao
        FROM anexos a
        JOIN transacoes t ON a.transacao_id = t.id
        JOIN subcategorias s ON t.subcategoria_id = s.id
        JOIN categorias c ON s.categoria_id = c.id
        JOIN meses m ON c.mes_id = m.id
        WHERE a.consistente = 0
    """)
    inconsistent_attachments = cursor.fetchall()
    if inconsistent_attachments:
        report.append("## ⚠️ Anexos Inconsistentes")
        for nome, caminho, motivo, t_desc, mes_exib in inconsistent_attachments:
            motivo_fmt = format_motivo(motivo)
            report.append(f"- **{mes_exib} > {nome}** (Anexo da transação '{t_desc}')")
            report.append(f"  - *Caminho*: `{caminho}`")
            report.append(f"  - *Motivo*: {motivo_fmt}")
        report.append("")
        
    # Verificar se existem arquivos físicos de anexos ausentes no disco
    cursor.execute("""
        SELECT a.nome_original, a.caminho_local, t.descricao, m.exibicao
        FROM anexos a
        JOIN transacoes t ON a.transacao_id = t.id
        JOIN subcategorias s ON t.subcategoria_id = s.id
        JOIN categorias c ON s.categoria_id = c.id
        JOIN meses m ON c.mes_id = m.id
    """)
    all_attachments = cursor.fetchall()
    missing_files = []
    for nome, caminho, t_desc, mes_exib in all_attachments:
        if caminho and not os.path.exists(caminho):
            missing_files.append((nome, caminho, t_desc, mes_exib))
            
    if missing_files:
        report.append("## 🔴 Arquivos de Anexos Ausentes no Disco")
        for nome, caminho, t_desc, mes_exib in missing_files:
            report.append(f"- **{mes_exib} > {nome}** (Transação: '{t_desc}')")
            report.append(f"  - *Caminho Esperado*: `{caminho}`")
        report.append("")
    else:
        report.append("## 🟢 Integridade de Arquivos Físicos")
        report.append("- Todos os anexos registrados no banco de dados estão presentes fisicamente no disco.")
        report.append("")

    conn.close()
    
    # Escrever relatório em markdown
    report_content = "\n".join(report)
    report_file = "relatorio_consistencia.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Relatório de consistência gravado em '{report_file}'.")

if __name__ == "__main__":
    check_consistency()
