import os
import sqlite3

def migrate_db(db_path=None, conn=None):
    """
    Migração: Adiciona a coluna condominio_id nas tabelas meses, membros_gestao e auditoria,
    relacionando-as com a tabela raiz condominio via FK.
    
    - meses.condominio_id: preenchido com o id do condomínio existente no banco (se houver).
    - membros_gestao.condominio_id: preenchido com o id do condomínio existente no banco.
    - auditoria.condominio_id: permanece NULL (campo opcional conforme issue #15).
    
    Resolve: issue #15
    """
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

    # Obtém o condominio_id existente (se houver) para propagar nas tabelas
    cursor.execute("SELECT id FROM condominio LIMIT 1")
    row = cursor.fetchone()
    condo_id = row[0] if row else None
    if condo_id:
        print(f"Condomínio encontrado: id='{condo_id}'. Será propagado para meses e membros_gestao.")
    else:
        print("Nenhum condomínio encontrado. As colunas condominio_id serão adicionadas com valor NULL.")

    # -------------------------------------------
    # 1. Tabela: meses
    # -------------------------------------------
    cursor.execute("PRAGMA table_info(meses)")
    colunas_meses = [col[1] for col in cursor.fetchall()]
    if "condominio_id" not in colunas_meses:
        print("Adicionando coluna 'condominio_id' na tabela 'meses'...")
        cursor.execute("ALTER TABLE meses ADD COLUMN condominio_id TEXT REFERENCES condominio(id)")
        if condo_id:
            cursor.execute("UPDATE meses SET condominio_id = ?", (condo_id,))
            cursor.execute("SELECT changes()")
            n = cursor.fetchone()[0]
            print(f"  {n} registro(s) de meses atualizado(s) com condominio_id='{condo_id}'.")
        conn.commit()
    else:
        print("A coluna 'condominio_id' já existe na tabela 'meses'. Pulando.")

    # -------------------------------------------
    # 2. Tabela: membros_gestao
    # -------------------------------------------
    cursor.execute("PRAGMA table_info(membros_gestao)")
    colunas_mg = [col[1] for col in cursor.fetchall()]
    if "condominio_id" not in colunas_mg:
        print("Adicionando coluna 'condominio_id' na tabela 'membros_gestao'...")
        cursor.execute("ALTER TABLE membros_gestao ADD COLUMN condominio_id TEXT REFERENCES condominio(id)")
        if condo_id:
            cursor.execute("UPDATE membros_gestao SET condominio_id = ?", (condo_id,))
            cursor.execute("SELECT changes()")
            n = cursor.fetchone()[0]
            print(f"  {n} registro(s) de membros_gestao atualizado(s) com condominio_id='{condo_id}'.")
        conn.commit()
    else:
        print("A coluna 'condominio_id' já existe na tabela 'membros_gestao'. Pulando.")

    # -------------------------------------------
    # 3. Tabela: auditoria
    # -------------------------------------------
    cursor.execute("PRAGMA table_info(auditoria)")
    colunas_aud = [col[1] for col in cursor.fetchall()]
    if "condominio_id" not in colunas_aud:
        print("Adicionando coluna 'condominio_id' na tabela 'auditoria'...")
        # Auditoria: condominio_id é opcional (NULL), conforme issue #15
        cursor.execute("ALTER TABLE auditoria ADD COLUMN condominio_id TEXT REFERENCES condominio(id)")
        conn.commit()
        print("  Coluna adicionada com valor NULL (campo opcional para auditoria).")
    else:
        print("A coluna 'condominio_id' já existe na tabela 'auditoria'. Pulando.")

    if should_close:
        conn.close()

    print("\nMigração concluída com sucesso!")
    print("Resumo:")
    print("  - meses.condominio_id       : adicionado" + (f" e preenchido com '{condo_id}'" if condo_id else " (NULL)"))
    print("  - membros_gestao.condominio_id: adicionado" + (f" e preenchido com '{condo_id}'" if condo_id else " (NULL)"))
    print("  - auditoria.condominio_id   : adicionado (NULL - será preenchido nas próximas execuções)")


if __name__ == "__main__":
    migrate_db()
