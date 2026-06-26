import xml.etree.ElementTree as ET


TIPOS_VALIDOS = [
    'facturaElectronica',
    'tiqueteElectronico',
    'facturaElectronicaCompra',
    'facturaElectronicaExportacion',
    'notaCreditoElectronica',
    'notaDebitoElectronica',
]

# La <Tarifa> (%) determina el bucket real de IVA, NO el <Codigo>.
# El esquema DGT CR v4.x usa código 01 y 08 para IVA genérico;
# los códigos 05, 06, 07 son exenciones/exoneraciones (no se suman).
CODIGOS_IVA_EXENTOS = {'05', '06', '07'}

TARIFA_A_CAMPO = {
    1.0:  'iva_1',
    2.0:  'iva_2',
    4.0:  'iva_4',
    13.0: 'iva_13',
}


def _safe_float(el):
    try:
        return float(el.text) if el is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def parsear_xml(contenido_xml):
    try:
        root = ET.fromstring(contenido_xml)
        tag_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag

        if not any(t.lower() in tag_local.lower() for t in TIPOS_VALIDOS):
            return None

        ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        prefix = f'{{{ns}}}' if ns else ''

        clave = root.find(f'{prefix}Clave')
        clave = clave.text if clave is not None else None

        emisor = root.find(f'{prefix}Emisor/{prefix}Nombre')
        emisor = emisor.text if emisor is not None else 'Desconocido'

        fecha = root.find(f'{prefix}FechaEmision')
        fecha = fecha.text[:10] if fecha is not None else None

        resumen = root.find(f'{prefix}ResumenFactura')
        monto_sin_iva = _safe_float(resumen.find(f'{prefix}TotalVentaNeta') if resumen is not None else None)
        monto_total   = _safe_float(resumen.find(f'{prefix}TotalComprobante') if resumen is not None else None)

        iva = {'iva_13': 0.0, 'iva_1': 0.0, 'iva_2': 0.0, 'iva_4': 0.0}

        for linea in root.findall(f'{prefix}DetalleServicio/{prefix}LineaDetalle'):
            for impuesto in linea.findall(f'{prefix}Impuesto'):  # findall = todos los impuestos por línea
                codigo_el = impuesto.find(f'{prefix}Codigo')
                monto_el  = impuesto.find(f'{prefix}Monto')
                tarifa_el = impuesto.find(f'{prefix}Tarifa')

                if codigo_el is None or monto_el is None:
                    continue
                if codigo_el.text in CODIGOS_IVA_EXENTOS:
                    continue

                monto_imp  = _safe_float(monto_el)
                tarifa     = _safe_float(tarifa_el)
                campo      = TARIFA_A_CAMPO.get(round(tarifa, 0), 'iva_13')  # fallback seguro a 13%
                iva[campo] += monto_imp

        iva_total = sum(iva.values())

        return {
            'clave':               clave,
            'emisor':              emisor,
            'fecha_recibido':      fecha,
            'monto_sin_iva':       round(monto_sin_iva, 2),
            'iva_13':              round(iva['iva_13'], 2),
            'iva_1':               round(iva['iva_1'],  2),
            'iva_2':               round(iva['iva_2'],  2),
            'iva_4':               round(iva['iva_4'],  2),
            'iva_total':           round(iva_total, 2),
            'monto_total_con_iva':  round(monto_total, 2),
        }

    except Exception as e:
        print(f'❌ Error parseando XML: {e}')
        return None