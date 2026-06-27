import calendar
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def _normalizar_clave(clave):
    if clave is None:
        return None
    clave = str(clave).strip()
    return clave or None


def ya_existe(clave):
    clave = _normalizar_clave(clave)
    if not clave:
        return False

    result = (
        supabase.table("facturas")
        .select("id")
        .eq("clave", clave)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def guardar_factura(data):
    try:
        clave = _normalizar_clave(data.get("clave"))
        data["clave"] = clave

        if ya_existe(clave):
            print(f"⚠️ Duplicado ignorado: {data.get('emisor')}")
            return

        supabase.table("facturas").insert(data).execute()
        print(f"✅ Guardado: {data.get('emisor')}")

    except Exception as e:
        print(f"❌ Error guardando en DB: {e}")


def obtener_facturas_del_mes(anio, mes):
    desde = f"{anio}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    hasta = f"{anio}-{mes:02d}-{ultimo_dia:02d}"

    result = (
        supabase.table("facturas")
        .select("*")
        .gte("fecha_recibido", desde)
        .lte("fecha_recibido", hasta)
        .execute()
    )
    return result.data