from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

result = supabase.table('facturas').delete().neq('id', 0).execute()
print(f"🗑️ Registros eliminados: {len(result.data)}")