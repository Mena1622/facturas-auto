import datetime
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, CORREO_DESTINO


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
AZUL_OSCURO = colors.HexColor("#1B2A4A")
AZUL_MEDIO = colors.HexColor("#2E5090")
GRIS_CLARO = colors.HexColor("#F7F9FC")
GRIS_BORDE = colors.HexColor("#D0D7E3")
VERDE_TOTAL = colors.HexColor("#2E7D32")
BLANCO = colors.white
NEGRO = colors.HexColor("#1B2A4A")


def autenticar_gmail():
    token_data = os.getenv("GMAIL_TOKEN")
    if token_data:
        with open('token.json', 'w') as f:
            f.write(token_data)
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)


def formato_colones(monto):
    return f"₡{monto:,.2f}"


def obtener_facturas_del_mes(anio, mes):
    desde = f"{anio}-{mes:02d}-01"
    hasta = f"{anio}-{mes:02d}-31"
    result = (
        supabase.table('facturas')
        .select('*')
        .gte('fecha_recibido', desde)
        .lte('fecha_recibido', hasta)
        .execute()
    )
    return result.data


def enviar_por_gmail(service, archivo, nombre_mes):
    msg = MIMEMultipart()
    msg['To'] = CORREO_DESTINO
    msg['Subject'] = f"Reporte de Facturas Electrónicas - {nombre_mes}"
    msg.attach(MIMEText(
        f"Adjunto el reporte de facturas electrónicas correspondiente a {nombre_mes}.",
        'plain'
    ))
    with open(archivo, 'rb') as f:
        adjunto = MIMEBase('application', 'octet-stream')
        adjunto.set_payload(f.read())
        encoders.encode_base64(adjunto)
        adjunto.add_header(
            'Content-Disposition',
            f'attachment; filename="{os.path.basename(archivo)}"'
        )
        msg.attach(adjunto)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f"📧 Reporte enviado a {CORREO_DESTINO}")


def generar_reporte(anio=None, mes=None):
    hoy = datetime.date.today()
    anio = anio or hoy.year
    mes = mes or hoy.month
    nombre_mes = datetime.date(anio, mes, 1).strftime("%B %Y").capitalize()

    facturas = obtener_facturas_del_mes(anio, mes)
    if not facturas:
        print(f"📭 No hay facturas para {nombre_mes}")
        return

    distribuidores = {}
    for f in facturas:
        emisor = f.get('emisor', 'Desconocido')
        if emisor not in distribuidores:
            distribuidores[emisor] = {
                'cantidad': 0, 'monto_sin_iva': 0,
                'iva_1': 0, 'iva_2': 0, 'iva_4': 0, 'iva_13': 0,
                'iva_total': 0, 'monto_total_con_iva': 0
            }
        d = distribuidores[emisor]
        d['cantidad'] += 1
        d['monto_sin_iva'] += f.get('monto_sin_iva', 0)
        d['iva_1'] += f.get('iva_1', 0)
        d['iva_2'] += f.get('iva_2', 0)
        d['iva_4'] += f.get('iva_4', 0)
        d['iva_13'] += f.get('iva_13', 0)
        d['iva_total'] += f.get('iva_total', 0)
        d['monto_total_con_iva'] += f.get('monto_total_con_iva', 0)

    total_sin_iva = sum(d['monto_sin_iva'] for d in distribuidores.values())
    total_iva_1 = sum(d['iva_1'] for d in distribuidores.values())
    total_iva_2 = sum(d['iva_2'] for d in distribuidores.values())
    total_iva_4 = sum(d['iva_4'] for d in distribuidores.values())
    total_iva_13 = sum(d['iva_13'] for d in distribuidores.values())
    total_iva = sum(d['iva_total'] for d in distribuidores.values())
    total_con_iva = sum(d['monto_total_con_iva'] for d in distribuidores.values())

    nombre_archivo = f"reporte_{anio}_{mes:02d}.pdf"
    doc = SimpleDocTemplate(
        nombre_archivo, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    elementos = []

    titulo_style = ParagraphStyle('titulo', fontSize=22, textColor=AZUL_OSCURO,
                                  fontName='Helvetica-Bold', alignment=1, spaceAfter=8)
    mes_style = ParagraphStyle('mes', fontSize=14, textColor=AZUL_MEDIO,
                               fontName='Helvetica-Bold', alignment=1, spaceBefore=6, spaceAfter=6)
    meta_style = ParagraphStyle('meta', fontSize=8, textColor=colors.HexColor("#7F8C8D"),
                                fontName='Helvetica', alignment=1, spaceBefore=4, spaceAfter=0)

    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(Paragraph("Reporte de Facturas Electrónicas", titulo_style))
    elementos.append(Paragraph(nombre_mes, mes_style))
    elementos.append(Paragraph(
        f"Generado el {hoy.strftime('%d de %B de %Y')} · "
        f"{len(facturas)} factura{'s' if len(facturas) != 1 else ''} procesada{'s' if len(facturas) != 1 else ''}",
        meta_style
    ))
    elementos.append(Spacer(1, 0.5*cm))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=AZUL_OSCURO))
    elementos.append(Spacer(1, 0.5*cm))

    def th(t): return Paragraph(t, ParagraphStyle('th', fontSize=8, textColor=BLANCO, fontName='Helvetica-Bold', alignment=1))
    def td(t): return Paragraph(t, ParagraphStyle('td', fontSize=8, textColor=NEGRO, fontName='Helvetica', alignment=2))
    def tdl(t): return Paragraph(t, ParagraphStyle('tdl', fontSize=8, textColor=NEGRO, fontName='Helvetica', alignment=0))
    def tt(t): return Paragraph(t, ParagraphStyle('tt', fontSize=8, textColor=BLANCO, fontName='Helvetica-Bold', alignment=2))
    def ttl(t): return Paragraph(t, ParagraphStyle('ttl', fontSize=8, textColor=BLANCO, fontName='Helvetica-Bold', alignment=0))

    filas = [[
        th('Distribuidor'), th('Fact.'), th('Sin IVA'),
        th('IVA 1%'), th('IVA 2%'), th('IVA 4%'),
        th('IVA 13%'), th('Total IVA'), th('Total')
    ]]

    for emisor, d in sorted(distribuidores.items()):
        filas.append([
            tdl(emisor), td(str(d['cantidad'])),
            td(formato_colones(d['monto_sin_iva'])),
            td(formato_colones(d['iva_1'])),
            td(formato_colones(d['iva_2'])),
            td(formato_colones(d['iva_4'])),
            td(formato_colones(d['iva_13'])),
            td(formato_colones(d['iva_total'])),
            td(formato_colones(d['monto_total_con_iva'])),
        ])

    filas.append([
        ttl('TOTAL GENERAL'), tt(str(len(facturas))),
        tt(formato_colones(total_sin_iva)),
        tt(formato_colones(total_iva_1)),
        tt(formato_colones(total_iva_2)),
        tt(formato_colones(total_iva_4)),
        tt(formato_colones(total_iva_13)),
        tt(formato_colones(total_iva)),
        tt(formato_colones(total_con_iva)),
    ])

    tabla = Table(filas, colWidths=[4.8*cm, 1.2*cm, 2.6*cm, 1.6*cm, 1.6*cm, 1.6*cm, 2.0*cm, 2.2*cm, 2.6*cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), AZUL_OSCURO),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [BLANCO, GRIS_CLARO]),
        ('TOPPADDING', (0, 1), (-1, -2), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, -1), (-1, -1), VERDE_TOTAL),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, GRIS_BORDE),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, AZUL_OSCURO),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, VERDE_TOTAL),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 0.8*cm))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_BORDE))
    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(Paragraph(
        f"Sin IVA: <b>{formato_colones(total_sin_iva)}</b>"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;Total IVA: <b>{formato_colones(total_iva)}</b>"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;Total con IVA: <b>{formato_colones(total_con_iva)}</b>",
        ParagraphStyle('res', fontSize=9, textColor=AZUL_MEDIO, fontName='Helvetica', alignment=1, leading=16)
    ))

    doc.build(elementos)
    print(f"✅ Reporte generado: {nombre_archivo}")

    try:
        service = autenticar_gmail()
        enviar_por_gmail(service, nombre_archivo, nombre_mes)
        os.remove(nombre_archivo)
        print(f"🗑️ PDF eliminado: {nombre_archivo}")
        print("Se envió correctamente el reporte.")
    except Exception as e:
        print(f"❌ Error enviando el reporte: {e}")


if __name__ == "__main__":
    generar_reporte()