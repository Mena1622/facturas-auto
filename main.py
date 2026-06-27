import base64
import os
import time
import datetime
import email
from email import policy as email_policy
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from parser import parsear_xml
from database import guardar_factura, ya_existe
from config import CORREO_DESTINO, CORREO_ORIGEN, ETIQUETA_GMAIL, LIMITE_CORREOS_TEST


SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
]


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
    print("Etiquetas disponibles en Gmail API:")
    for label in labels.get('labels', []):
        print(f"- [{label['name']}]")
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


def reenviar_correo(service, msg_id, destino, reintentos=3, espera=5):
    """
    Reenvía el correo de forma FIEL al original.
    Obtiene el RAW completo y modifica SOLO los headers To:/From:/Message-ID,
    dejando body, HTML, adjuntos e imágenes inline 100% intactos.
    Reintenta hasta `reintentos` veces ante errores transitorios.
    """
    msg_raw = service.users().messages().get(
        userId='me', id=msg_id, format='raw').execute()

    raw_bytes = base64.urlsafe_b64decode(msg_raw['raw'])
    original = email.message_from_bytes(raw_bytes, policy=email_policy.compat32)

    for header in ['To', 'Cc', 'Bcc', 'From', 'Message-ID',
                   'DKIM-Signature', 'ARC-Seal',
                   'ARC-Message-Signature', 'ARC-Authentication-Results']:
        del original[header]

    original['From'] = CORREO_ORIGEN
    original['To'] = destino

    raw_modificado = base64.urlsafe_b64encode(
        original.as_bytes(unixfrom=False)).decode('utf-8')

    for intento in range(1, reintentos + 1):
        try:
            service.users().messages().send(
                userId='me', body={'raw': raw_modificado}).execute()
            return  # éxito
        except Exception as e:
            print(f"⚠️  Intento {intento}/{reintentos} fallido para {msg_id}: {e}")
            if intento < reintentos:
                time.sleep(espera * intento)  # espera 5s, 10s, 15s...
            else:
                raise  # agotó reintentos, propagar el error


def etiquetar_correo(service, msg_id, label_id):
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'addLabelIds': [label_id]}
    ).execute()


def procesar_correos():
    print(f"\n🔍 Iniciando procesamiento - {datetime.datetime.now()}")
    service = autenticar_gmail()

    perfil = service.users().getProfile(userId='me').execute()
    print(f"Cuenta autenticada: {perfil.get('emailAddress')}")

    label_id = obtener_id_etiqueta(service, ETIQUETA_GMAIL)

    if not label_id:
        print(f"❌ No se encontró la etiqueta '{ETIQUETA_GMAIL}'")
        return

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

        print(f" Procesando msg_id={msg_id} | etiquetas={label_ids}")

        if label_id in label_ids:
            continue

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
            print(f"❌ Error al procesar {msg_id} luego de {3} intentos: {e}")


if __name__ == "__main__":
    procesar_correos()