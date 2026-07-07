import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'scripts'))

from run_dashboard import Api

api = Api()
print("Initial condo_id:", api.condo_id)

result = api.set_condominio("12345")
print("Set result:", result)
