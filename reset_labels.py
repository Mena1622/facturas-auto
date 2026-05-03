import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from config import ETIQUETA_GMAIL

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

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

def reset_etiquetas():
    service = autenticar_gmail()
    labels = service.users().labels().list(userId='me').execute()
    label_id = next((l['id'] for l in labels.get('labels', []) if l['name'] == ETIQUETA_GMAIL), None)

    if not label_id:
        print(f"❌ Etiqueta '{ETIQUETA_GMAIL}' no encontrada")
        return

    results = service.users().messages().list(
        userId='me', q=f"label:{ETIQUETA_GMAIL}", maxResults=500).execute()
    mensajes = results.get('messages', [])

    print(f"🔍 {len(mensajes)} correos con etiqueta '{ETIQUETA_GMAIL}'")

    for msg in mensajes:
        service.users().messages().modify(
            userId='me',
            id=msg['id'],
            body={'removeLabelIds': [label_id]}
        ).execute()

    print(f"✅ Etiqueta removida de {len(mensajes)} correos")

if __name__ == "__main__":
    reset_etiquetas()