# Renovar `GMAIL_TOKEN` para `facturas-auto`

Este documento explica cómo volver a generar el token de Gmail cuando GitHub Actions falle por expiración, revocación o formato incorrecto del token. El proyecto actual lee el secret `GMAIL_TOKEN`, lo escribe como `token.json` y luego carga ese archivo con `Credentials.from_authorized_user_file('token.json', SCOPES)`, por lo que `GMAIL_TOKEN` debe contener el **contenido completo de `token.json`** y no el JSON del cliente OAuth.[cite:192]

## Qué significa cada archivo

- `credentials.json`: archivo descargado desde Google Cloud con `client_id`, `client_secret`, `auth_uri` y `token_uri`; sirve para iniciar el flujo OAuth.[cite:203][cite:87]
- `token.json`: archivo generado después de iniciar sesión con Google; contiene el access token, refresh token, scopes y datos de cliente que usa el código en GitHub Actions.[cite:192][cite:58][cite:81]
- Secret `GMAIL_TOKEN`: debe guardar el contenido completo de `token.json`, porque el código lo convierte nuevamente en `token.json` dentro del runner antes de autenticar Gmail.[cite:192]

## Cuándo hacer este proceso

Haz este proceso si en GitHub Actions aparece alguno de estos errores:

- `invalid_grant: Token has been expired or revoked`.[cite:2][cite:3]
- `JSONDecodeError` al leer `token.json`, señal de que `GMAIL_TOKEN` tiene contenido inválido o incompleto.[cite:192]
- `invalid_client`, señal de que el `client_secret` del `credentials.json` ya no sirve y debes descargar o generar uno nuevo.[cite:115][cite:203]

## Paso 1: entrar a Google Cloud correcto

Entra al proyecto de Google Cloud que usa esta automatización y asegúrate de estar usando la cuenta del **correo origen real** del buzón que se leerá con Gmail API. Si el sistema procesa el buzón de `CORREO_ORIGEN`, el login OAuth para generar el token debe hacerse con esa misma cuenta para que el token quede ligado al buzón correcto.[cite:190][cite:84][cite:105]

## Paso 2: revisar el cliente OAuth

En Google Cloud, ve a **Google Auth Platform → Clients** y abre el cliente de tipo **Desktop app**. Si el `client_secret` viejo falla o no estás seguro de que siga vigente, crea un secret nuevo con **Add secret** y descarga de nuevo el JSON completo del cliente OAuth.[cite:115][cite:121]

## Paso 3: preparar `credentials.json`

Descarga el JSON del cliente OAuth y guárdalo en la carpeta del proyecto con el nombre `credentials.json`. Ese archivo debe tener estructura `installed` con `client_id`, `client_secret`, `auth_uri`, `token_uri` y `redirect_uris`, como el archivo que se adjuntó en esta conversación.[cite:203][cite:87]

## Paso 4: instalar dependencias en Windows

En PowerShell, dentro de la carpeta del proyecto, usa el launcher `py` para comprobar Python e instalar las librerías necesarias para generar el token OAuth. En esta conversación funcionó `py --version` con Python 3.14.4 y luego la instalación de `google-auth-oauthlib`, `google-api-python-client` y `google-auth-httplib2`.[cite:204][cite:219]

Comandos:

```powershell
py --version
py -m pip install google-auth-oauthlib google-api-python-client google-auth-httplib2
```

## Paso 5: crear el script temporal para generar token

Crea un archivo temporal llamado `crear_token.py` en la carpeta del proyecto con este contenido, usando los mismos scopes que usa `main.py` (`gmail.modify` y `gmail.send`). Esos scopes coinciden con el código real del proyecto adjuntado.[cite:192]

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send"
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as token:
    token.write(creds.to_json())

print("token.json generado")
```

## Paso 6: generar `token.json`

Ejecuta el script desde PowerShell:

```powershell
py crear_token.py
```

Se abrirá Google para autorizar la aplicación. Inicia sesión con el correo del buzón real que usa `CORREO_ORIGEN` y acepta los permisos solicitados para Gmail.[cite:190][cite:84][cite:150]

Cuando el flujo termine, se generará un archivo `token.json` en la carpeta del proyecto. Ese archivo es el que realmente necesita GitHub Actions para volver a funcionar.[cite:58][cite:81]

## Paso 7: actualizar GitHub Actions

Ve al repositorio en GitHub:

1. **Settings**.
2. **Secrets and variables**.
3. **Actions**.
4. Edita **`GMAIL_TOKEN`**.
5. Borra el valor anterior.
6. Pega el contenido completo de `token.json`.
7. Guarda el secret.[cite:146][cite:192]

No pegues en `GMAIL_TOKEN` el JSON descargado de Google Cloud (`credentials.json`) ni el `client_secret` suelto, porque el código espera un `token.json` válido y completo.[cite:192][cite:203]

## Paso 8: volver a correr el workflow

Después de actualizar `GMAIL_TOKEN`, vuelve a ejecutar GitHub Actions. Si el token está bien generado y corresponde al buzón correcto, el proyecto podrá autenticar, refrescar credenciales y continuar con el procesamiento de correos como antes.[cite:192][cite:58]

## Qué secretos no debes tocar

Para este problema no hace falta cambiar estos secrets:

- `CORREO_DESTINO`.[cite:76]
- `CORREO_ORIGEN`.[cite:76]
- `CORREO_REPORTE_DESTINO`.[cite:76]
- `ETIQUETA_GMAIL`.[cite:76]
- `SUPABASE_KEY`.[cite:76]
- `SUPABASE_URL`.[cite:76]

El único secret que se reemplaza en este proceso es `GMAIL_TOKEN`.[cite:192]

## Errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| `invalid_grant: Token has been expired or revoked` | El refresh token ya no sirve.[cite:2][cite:3] | Generar `token.json` nuevo y reemplazar `GMAIL_TOKEN`.[cite:58] |
| `JSONDecodeError` al leer `token.json` | `GMAIL_TOKEN` tiene texto roto, incompleto o el JSON equivocado.[cite:192] | Pegar el `token.json` completo, no `credentials.json`.[cite:203][cite:192] |
| `invalid_client` | El `client_secret` del cliente OAuth ya no es válido.[cite:115] | Crear un secret nuevo en Google Cloud, descargar `credentials.json` nuevo y regenerar `token.json`.[cite:121][cite:203] |
| `ModuleNotFoundError: No module named 'google_auth_oauthlib'` | Faltan dependencias locales para generar el token.[cite:219] | Ejecutar `py -m pip install google-auth-oauthlib google-api-python-client google-auth-httplib2`.[cite:219] |

## Resumen rápido

1. Entrar a Google Cloud del correo origen correcto.[cite:84][cite:105]
2. Revisar o regenerar el cliente Desktop OAuth.[cite:115]
3. Descargar el JSON del cliente y guardarlo como `credentials.json`.[cite:203]
4. Instalar dependencias locales con `py -m pip install ...`.[cite:219]
5. Ejecutar `py crear_token.py`.[cite:58]
6. Iniciar sesión con el correo origen.[cite:105]
7. Copiar el `token.json` generado a `GMAIL_TOKEN`.[cite:192]
8. Reintentar GitHub Actions.[cite:192]
