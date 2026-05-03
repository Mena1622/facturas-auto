import xml.etree.ElementTree as ET

TIPOS_VALIDOS = [
    'facturaElectronica',
    'tiqueteElectronico',
    'facturaElectronicaCompra',
    'facturaElectronicaExportacion',
    'notaCreditoElectronica',
    'notaDebitoElectronica',
]

CODIGOS_IVA = {
    "01": "iva_13", "02": "iva_1", "03": "iva_2",
    "04": "iva_4", "05": "iva_0", "06": "iva_0",
    "07": "iva_0", "08": "iva_13"
}

def parsear_xml(contenido_xml):
    try:
        root = ET.fromstring(contenido_xml)
        tag_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag

        if not any(t.lower() in tag_local.lower() for t in TIPOS_VALIDOS):
            return None

        ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        prefix = f"{{{ns}}}" if ns else ""

        clave = root.find(f"{prefix}Clave")
        clave = clave.text if clave is not None else None

        emisor = root.find(f"{prefix}Emisor/{prefix}Nombre")
        emisor = emisor.text if emisor is not None else "Desconocido"

        fecha = root.find(f"{prefix}FechaEmision")
        fecha = fecha.text[:10] if fecha is not None else None

        resumen = root.find(f"{prefix}ResumenFactura")
        monto_sin_iva = float(resumen.find(f"{prefix}TotalVentaNeta").text) if resumen is not None else 0.0
        monto_total = float(resumen.find(f"{prefix}TotalComprobante").text) if resumen is not None else 0.0

        iva = {"iva_13": 0.0, "iva_1": 0.0, "iva_2": 0.0, "iva_4": 0.0, "iva_0": 0.0}

        for linea in root.findall(f"{prefix}DetalleServicio/{prefix}LineaDetalle"):
            impuesto = linea.find(f"{prefix}Impuesto")
            if impuesto is not None:
                codigo = impuesto.find(f"{prefix}Codigo")
                monto_imp = impuesto.find(f"{prefix}Monto")
                if codigo is not None and monto_imp is not None:
                    campo = CODIGOS_IVA.get(codigo.text, "iva_0")
                    iva[campo] += float(monto_imp.text)

        iva_total = sum([iva["iva_13"], iva["iva_1"], iva["iva_2"], iva["iva_4"]])

        return {
            "clave": clave,
            "emisor": emisor,
            "fecha_recibido": fecha,
            "monto_sin_iva": round(monto_sin_iva, 2),
            "iva_13": round(iva["iva_13"], 2),
            "iva_1": round(iva["iva_1"], 2),
            "iva_2": round(iva["iva_2"], 2),
            "iva_4": round(iva["iva_4"], 2),
            "iva_total": round(iva_total, 2),
            "monto_total_con_iva": round(monto_total, 2),
        }
    except Exception as e:
        print(f"❌ Error parseando XML: {e}")
        return None