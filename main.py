import base64
import os
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from parser import parsear_xml
from database import guardar_factura, ya_existe
from config import CORREO_DESTINO, ETIQUETA_GMAIL, LIMITE_CORREOS_TEST

SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/gmail.send']

def autenticar_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
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
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg_original = service.users().messages().get(userId='me', id=msg_id).execute()
    headers = msg_original.get('payload', {}).get('headers', [])
    asunto = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Factura Electrónica')

    nuevo = MIMEMultipart()
    nuevo['To'] = destino
    nuevo['Subject'] = f"FWD: {asunto}"
    nuevo.attach(MIMEText("Factura electrónica reenviada automáticamente por facturas-auto.", 'plain'))

    partes = collect_parts(msg_original.get('payload', {}))
    for parte in partes:
        nombre = parte.get('filename', '')
        if nombre.lower().endswith('.xml') or nombre.lower().endswith('.pdf'):
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
        print(f"❌ No se encontró la etiqueta '{ETIQUETA_GMAIL}' en Gmail")
        return

    # ✅ -subject:FWD excluye los reenvíos generados por este mismo script
    query = f"-label:{ETIQUETA_GMAIL} -from:mgamboafacturas@gmail.com -subject:FWD"
    results = service.users().messages().list(
        userId='me', q=query, maxResults=LIMITE_CORREOS_TEST).execute()
    mensajes = results.get('messages', [])

    if not mensajes:
        print("📭 No hay correos nuevos para procesar")
        return

    print(f"📬 {len(mensajes)} correos encontrados")

    for msg in mensajes:
        msg_id = msg['id']
        xmls = tiene_adjunto_xml(service, msg_id)

        msg_debug = service.users().messages().get(userId='me', id=msg_id).execute()
        headers_debug = msg_debug.get('payload', {}).get('headers', [])
        asunto_debug = next((h['value'] for h in headers_debug if h['name'] == 'Subject'), 'Sin asunto')
        print(f"📧 {asunto_debug[:70]} | XMLs: {len(xmls)}")

        if not xmls:
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
            print(f"⏭️  Factura ya existe, omitiendo...")
            etiquetar_correo(service, msg_id, label_id)
            continue

        print(f"\n📄 Procesando correo con {len(facturas_validas)} factura(s)...")
        estado = "reenviado"

        try:
            reenviar_correo(service, msg_id, CORREO_DESTINO)
            etiquetar_correo(service, msg_id, label_id)
            print(f"✅ Reenviado a {CORREO_DESTINO}")
        except Exception as e:
            estado = "error_reenvio"
            print(f"❌ Error al reenviar: {e}")

        for _, _, datos in facturas_validas:
            if not ya_existe(datos.get('clave')):
                datos['estado'] = estado
                datos['fecha_reenvio'] = datetime.datetime.now().isoformat()
                guardar_factura(datos)
                print(f"✅ Guardado: {datos.get('emisor', 'Desconocido')}")

if __name__ == "__main__":
    procesar_correos()