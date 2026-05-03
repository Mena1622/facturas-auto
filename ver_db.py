# ver_db.py
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
result = supabase.table('facturas').select('*').execute()

for f in result.data:
    print(f"{f.get('fecha_recibido')} | {f.get('emisor')}")