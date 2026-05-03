import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

def es_xml_factura(nombre):
    n = nombre.lower()
    return n.endswith('.xml') and not any(p in n for p in ['resp', 'respuesta', 'mh-', '_ack', 'hacienda'])

def collect_parts(payload):
    result = []
    nombre = payload.get('filename', '')
    if nombre:
        result.append(nombre)
    for p in payload.get('parts', []):
        result += collect_parts(p)
    return result

def listar_archivos():
    service = autenticar_gmail()

    # ✅ Excluye FWDs generados por el script y correos sin adjuntos relevantes
    results = service.users().messages().list(
        userId='me',
        q="-subject:FWD",
        maxResults=20
    ).execute()
    mensajes = results.get('messages', [])

    correos_con_factura = 0
    correos_con_xml = 0
    total = len(mensajes)

    print(f"\n{'='*85}")
    print(f"{'#':<4} {'ASUNTO':<40} {'XML FACTURA':<35} {'XML RESPUESTA'}")
    print(f"{'='*85}")

    for i, msg in enumerate(mensajes, 1):
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data.get('payload', {}).get('headers', [])
        asunto = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Sin asunto')

        archivos = collect_parts(msg_data.get('payload', {}))
        xmls_todos = [a for a in archivos if a.lower().endswith('.xml')]
        xmls_factura = [a for a in xmls_todos if es_xml_factura(a)]
        xmls_respuesta = [a for a in xmls_todos if not es_xml_factura(a)]

        if xmls_todos:
            correos_con_xml += 1
        if xmls_factura:
            correos_con_factura += 1

        factura_str = xmls_factura[0][:33] if xmls_factura else '-'
        respuesta_str = xmls_respuesta[0][:33] if xmls_respuesta else '-'

        print(f"{i:<4} {asunto[:40]:<40} {factura_str:<35} {respuesta_str}")

    print(f"{'='*85}")
    print(f"📬 Total correos analizados:                    {total}")
    print(f"✅ Correos con al menos 1 XML (cualquier tipo): {correos_con_xml}")
    print(f"📄 Correos con XML de FACTURA real:             {correos_con_factura}")
    print(f"❌ Correos SIN adjuntos XML:                    {total - correos_con_xml}")

if __name__ == "__main__":
    listar_archivos()