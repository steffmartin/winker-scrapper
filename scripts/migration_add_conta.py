import os
import sqlite3
import re
import json

def migrate_db(db_path=None, conn=None):
    should_close = False
    if conn is None:
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            db_path = os.path.join(project_root, "database", "winker_data.db")
            
        print(f"Iniciando migração no banco de dados: {db_path}")
        if not os.path.exists(db_path):
            print("Banco de dados não encontrado. Nada a migrar.")
            return
            
        conn = sqlite3.connect(db_path)
        should_close = True
    else:
        print("Iniciando migração utilizando conexão fornecida.")
        
    cursor = conn.cursor()
    
    # 1. Adicionar a coluna no banco de dados se não existir
    cursor.execute("PRAGMA table_info(transacoes)")
    colunas = [col[1] for col in cursor.fetchall()]
    if "conta" not in colunas:
        print("Adicionando coluna 'conta' na tabela 'transacoes'...")
        cursor.execute("ALTER TABLE transacoes ADD COLUMN conta TEXT")
        conn.commit()
    else:
        print("A coluna 'conta' já existe na tabela 'transacoes'.")
        
    # 2. Preencher a coluna para os registros de transação existentes
    cursor.execute("SELECT id, descricao, consistente, motivo_inconsistencia FROM transacoes")
    transacoes = cursor.fetchall()
    
    total_atualizadas = 0
    total_inconsistentes = 0
    
    for row in transacoes:
        t_id, descricao, consistente, motivo_inconsistencia = row
        
        # Regex para extrair a conta
        conta = None
        if descricao:
            match = re.search(r"(?:Conta|CTA\.\s*PGTO)\s*:\s*([^-\n]+)", descricao, re.IGNORECASE)
            if match:
                conta = match.group(1).strip().upper()
                
        if conta:
            cursor.execute("UPDATE transacoes SET conta = ? WHERE id = ?", (conta, t_id))
            total_atualizadas += 1
        else:
            # Transações sem conta identificada também ficam 'inconsistentes'
            # Update consistente para 0 (false)
            novo_consistente = 0
            
            # Carregar motivos de inconsistência existentes
            reasons = []
            if motivo_inconsistencia:
                try:
                    reasons = json.loads(motivo_inconsistencia)
                    if not isinstance(reasons, list):
                        reasons = [str(reasons)]
                except json.JSONDecodeError:
                    reasons = [motivo_inconsistencia]
            
            if "Conta não identificada" not in reasons:
                reasons.append("Conta não identificada")
                
            novo_motivo = json.dumps(reasons, ensure_ascii=False)
            
            cursor.execute(
                "UPDATE transacoes SET consistente = ?, motivo_inconsistencia = ?, conta = NULL WHERE id = ?",
                (novo_consistente, novo_motivo, t_id)
            )
            total_inconsistentes += 1
            
    conn.commit()
    if should_close:
        conn.close()
    
    print(f"Migração concluída com sucesso!")
    print(f"- Transações com conta identificada e preenchida: {total_atualizadas}")
    print(f"- Transações marcadas como inconsistentes (sem conta): {total_inconsistentes}")

if __name__ == "__main__":
    migrate_db()
