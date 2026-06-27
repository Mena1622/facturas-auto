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
# En DGT CR v4.x, 05, 06 y 07 corresponden a exenciones/exoneraciones.
CODIGOS_IVA_EXENTOS = {'05', '06', '07'}

TARIFA_A_CAMPO = {
    1.0: 'iva_1',
    2.0: 'iva_2',
    4.0: 'iva_4',
    13.0: 'iva_13',
}


def _safe_float(el):
    try:
        if el is None or el.text is None:
            return 0.0
        return float(el.text)
    except (TypeError, ValueError):
        return 0.0


def _round2(valor):
    return round(float(valor or 0.0), 2)


def parsear_xml(contenido_xml):
    try:
        root = ET.fromstring(contenido_xml)
        tag_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag

        if not any(t.lower() in tag_local.lower() for t in TIPOS_VALIDOS):
            return None

        ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        prefix = f'{{{ns}}}' if ns else ''

        clave_el = root.find(f'{prefix}Clave')
        clave = clave_el.text.strip() if clave_el is not None and clave_el.text else None

        emisor_el = root.find(f'{prefix}Emisor/{prefix}Nombre')
        emisor = emisor_el.text.strip() if emisor_el is not None and emisor_el.text else 'Desconocido'

        fecha_el = root.find(f'{prefix}FechaEmision')
        fecha = fecha_el.text[:10] if fecha_el is not None and fecha_el.text else None

        resumen = root.find(f'{prefix}ResumenFactura')
        monto_sin_iva = _safe_float(resumen.find(f'{prefix}TotalVentaNeta') if resumen is not None else None)
        monto_total = _safe_float(resumen.find(f'{prefix}TotalComprobante') if resumen is not None else None)
        total_impuesto_resumen = _safe_float(resumen.find(f'{prefix}TotalImpuesto') if resumen is not None else None)

        iva = {
            'iva_13': 0.0,
            'iva_1': 0.0,
            'iva_2': 0.0,
            'iva_4': 0.0,
        }

        for linea in root.findall(f'{prefix}DetalleServicio/{prefix}LineaDetalle'):
            for impuesto in linea.findall(f'{prefix}Impuesto'):
                codigo_el = impuesto.find(f'{prefix}Codigo')
                monto_el = impuesto.find(f'{prefix}Monto')
                tarifa_el = impuesto.find(f'{prefix}Tarifa')

                codigo = codigo_el.text.strip() if codigo_el is not None and codigo_el.text else None
                if not codigo or monto_el is None:
                    continue

                if codigo in CODIGOS_IVA_EXENTOS:
                    continue

                monto_imp = _safe_float(monto_el)
                tarifa = round(_safe_float(tarifa_el), 0)

                campo = TARIFA_A_CAMPO.get(tarifa)
                if campo is None:
                    campo = 'iva_13'

                iva[campo] += monto_imp

        iva_total_detalle = sum(iva.values())
        iva_total = iva_total_detalle

        if total_impuesto_resumen > 0 and abs(total_impuesto_resumen - iva_total_detalle) > 0.02:
            iva_total = total_impuesto_resumen

        return {
            'clave': clave,
            'emisor': emisor,
            'fecha_recibido': fecha,
            'monto_sin_iva': _round2(monto_sin_iva),
            'iva_13': _round2(iva['iva_13']),
            'iva_1': _round2(iva['iva_1']),
            'iva_2': _round2(iva['iva_2']),
            'iva_4': _round2(iva['iva_4']),
            'iva_total': _round2(iva_total),
            'monto_total_con_iva': _round2(monto_total),
        }

    except Exception as e:
        print(f'❌ Error parseando XML: {e}')
        return None