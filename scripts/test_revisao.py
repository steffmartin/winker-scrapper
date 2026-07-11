import os
import sys
from models import db, Meses, Categorias, Subcategorias, Transacoes, Condominio, Anexos, PrestacoesContas
from run_dashboard import Api

def run_tests():
    print("Iniciando testes da Tela de Revisão...")
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'winker.db')
    db.init(db_path)
    db.connect()

    api = Api()
    # Pega o primeiro condominio para testar
    condo = Condominio.select().first()
    if not condo:
        print("Nenhum condomínio encontrado. Crie dados na base primeiro.")
        return
    
    api.condo_id = condo.id
    api.init_error = None

    print(f"Condomínio base: {condo.nome}")

    # Test get_pendencias_revisao_count
    count_res = api.get_pendencias_revisao_count()
    print("get_pendencias_revisao_count:", count_res)

    # Test get_registros_nao_revisados
    for tipo in ['meses', 'categorias', 'subcategorias', 'lancamentos', 'documentos']:
        res = api.get_registros_nao_revisados(tipo)
        print(f"get_registros_nao_revisados({tipo}): status={res['status']}, count={len(res.get('data', []))}")
        
    print("Testes concluídos.")

if __name__ == '__main__':
    run_tests()
