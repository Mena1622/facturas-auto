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

def listar_bandeja():
    service = autenticar_gmail()

    # Sin ningún filtro — bandeja de entrada tal cual
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=30
    ).execute()
    mensajes = results.get('messages', [])

    print(f"\n{'='*60}")
    print(f"{'#':<4} {'ASUNTO'}")
    print(f"{'='*60}")

    for i, msg in enumerate(mensajes, 1):
        msg_data = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['Subject']).execute()
        headers = msg_data.get('payload', {}).get('headers', [])
        asunto = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Sin asunto')
        print(f"{i:<4} {asunto[:55]}")

    print(f"{'='*60}")
    print(f"Total: {len(mensajes)} correos")

if __name__ == "__main__":
    listar_bandeja()