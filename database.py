from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def ya_existe(clave):
    if not clave:
        return False
    result = supabase.table('facturas') \
        .select('id') \
        .eq('clave', clave) \
        .execute()
    return len(result.data) > 0

def guardar_factura(data):
    try:
        if ya_existe(data.get('clave')):
            print(f"⚠️ Duplicado ignorado: {data.get('emisor')}")
            return
        supabase.table('facturas').insert(data).execute()
        print(f"✅ Guardado: {data.get('emisor')}")
    except Exception as e:
        print(f"❌ Error guardando en DB: {e}")

def obtener_facturas_del_mes(anio, mes):
    desde = f"{anio}-{mes:02d}-01"
    hasta = f"{anio}-{mes:02d}-31"
    result = supabase.table('facturas') \
        .select('*') \
        .gte('fecha_recibido', desde) \
        .lte('fecha_recibido', hasta) \
        .execute()
    return result.data