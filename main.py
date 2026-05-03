import base64
import os
import json
import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from parser import parsear_xml
from database import guardar_factura, ya_existe
from config import CORREO_DESTINO, CORREO_ORIGEN, ETIQUETA_GMAIL, LIMITE_CORREOS_TEST

SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/gmail.send']

def autenticar_gmail():
    token_data = os.getenv("GMAIL_TOKEN")
    if token_data:
        with open('token.json', 'w') as f:
            f.write(token_data)
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

def obtener_id_etiqueta(service, nombre):
    labels = service.users().labels().list(userId='me').execute()
    for label in labels.get('labels', []):
        if label['name'] == nombre:
            return label['id']
    return None

def collect_parts(payload):
    result = []
    if payload.get('filename'):
        result.append(payload)
    for p in payload.get('parts', []):
        result += collect_parts(p)
    return result

def tiene_adjunto_xml(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id).execute()
    partes = collect_parts(msg.get('payload', {}))
    xmls = []
    for parte in partes:
        nombre = parte.get('filename', '')
        if nombre.lower().endswith('.xml'):
            attachment_id = parte.get('body', {}).get('attachmentId')
            if attachment_id:
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=attachment_id).execute()
                datos = base64.urlsafe_b64decode(att['data'])
                xmls.append((nombre, datos))
    return xmls

def reenviar_correo(service, msg_id, destino):
    msg_original = service.users().messages().get(userId='me', id=msg_id).execute()
    headers = msg_original.get('payload', {}).get('headers', [])
    asunto = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Factura Electrónica')

    nuevo = MIMEMultipart()
    nuevo['From'] = CORREO_ORIGEN
    nuevo['To'] = destino
    nuevo['Subject'] = f"FWD: {asunto}"
    nuevo.attach(MIMEText("Factura electrónica reenviada automáticamente por facturas-auto.", 'plain'))

    partes = collect_parts(msg_original.get('payload', {}))
    for parte in partes:
        nombre = parte.get('filename', '')
        if nombre.lower().endswith(('.xml', '.pdf')):
            attachment_id = parte.get('body', {}).get('attachmentId')
            if attachment_id:
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=attachment_id).execute()
                datos = base64.urlsafe_b64decode(att['data'])
                adjunto = MIMEBase('application', 'octet-stream')
                adjunto.set_payload(datos)
                encoders.encode_base64(adjunto)
                adjunto.add_header('Content-Disposition', f'attachment; filename="{nombre}"')
                nuevo.attach(adjunto)

    raw = base64.urlsafe_b64encode(nuevo.as_bytes()).decode('utf-8')
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

def etiquetar_correo(service, msg_id, label_id):
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'addLabelIds': [label_id]}
    ).execute()

def procesar_correos():
    print(f"\n🔍 Iniciando procesamiento - {datetime.datetime.now()}")
    service = autenticar_gmail()
    label_id = obtener_id_etiqueta(service, ETIQUETA_GMAIL)

    if not label_id:
        print(f"❌ No se encontró la etiqueta '{ETIQUETA_GMAIL}'")
        return

    # BUSCAMOS LOS ÚLTIMOS 10 CORREOS EN TOTAL
    query = f"-from:{CORREO_ORIGEN} -subject:FWD"
    results = service.users().messages().list(
        userId='me', q=query, maxResults=LIMITE_CORREOS_TEST).execute()
    
    mensajes = results.get('messages', [])
    if not mensajes:
        print("📭 No hay correos recientes.")
        return

    for msg in mensajes:
        msg_id = msg['id']
        msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
        label_ids = msg_data.get('labelIds', [])

        # SI YA TIENE ETIQUETA, IGNORAR Y PASAR AL SIGUIENTE
        if label_id in label_ids:
            continue

        # Si no tiene etiqueta, verificamos XML
        xmls = tiene_adjunto_xml(service, msg_id)
        if not xmls:
            print(f"⏭️  Sin XMLs, saltando correo {msg_id}")
            etiquetar_correo(service, msg_id, label_id)
            continue

        facturas_validas = []
        for nombre, contenido in xmls:
            datos = parsear_xml(contenido)
            if datos is not None:
                facturas_validas.append((nombre, contenido, datos))

        if not facturas_validas:
            etiquetar_correo(service, msg_id, label_id)
            continue

        hay_nuevas = any(not ya_existe(d.get('clave')) for _, _, d in facturas_validas)

        if not hay_nuevas:
            print(f"⏭️  Facturas ya procesadas previamente...")
            etiquetar_correo(service, msg_id, label_id)
            continue

        try:
            reenviar_correo(service, msg_id, CORREO_DESTINO)
            etiquetar_correo(service, msg_id, label_id)
            print(f"✅ Reenviado y etiquetado: {msg_id}")
            
            for _, _, datos in facturas_validas:
                if not ya_existe(datos.get('clave')):
                    datos['estado'] = "reenviado"
                    datos['fecha_reenvio'] = datetime.datetime.now().isoformat()
                    guardar_factura(datos)
        except Exception as e:
            print(f"❌ Error al procesar {msg_id}: {e}")

if __name__ == "__main__":
    procesar_correos()