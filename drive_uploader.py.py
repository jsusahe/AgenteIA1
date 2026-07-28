# drive_uploader.py
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# --- CONFIGURACIÓN ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']  # Permisos para crear archivos
PARENT_FOLDER_ID = 'AQUI_EL_ID_DE_TU_CARPETA_EN_DRIVE' # Opcional: ID de carpeta donde guardar
# ---------------------

def authenticate_drive():
    """Autentica con Google Drive y devuelve el servicio."""
    creds = None
    # El archivo token.json guarda las credenciales del usuario después del primer login
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # Si no hay credenciales válidas, inicia el flujo OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ Error: No se encuentra el archivo 'credentials.json'. Descárgalo de Google Cloud Console y colócalo aquí.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Error al construir el servicio de Drive: {e}")
        return None

def upload_file_to_drive(service, filename, filepath, mime_type):
    """Sube un archivo a Google Drive."""
    if not service:
        return None
    try:
        file_metadata = {'name': filename}
        if PARENT_FOLDER_ID:
            file_metadata['parents'] = [PARENT_FOLDER_ID]
        media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        file_id = file.get('id')
        print(f"✅ Archivo subido a Drive: {filename} (ID: {file_id})")
        return file_id
    except HttpError as error:
        print(f"❌ Ocurrió un error al subir {filename}: {error}")
        return None

def upload_daily_document(html_file, audio_file, html_mime='text/html', audio_mime='audio/mpeg'):
    """Función principal para subir ambos archivos."""
    service = authenticate_drive()
    if not service:
        print("❌ No se pudo autenticar con Drive.")
        return

    # Subir el HTML
    if os.path.exists(html_file):
        upload_file_to_drive(service, html_file, html_file, html_mime)
    else:
        print(f"⚠️ Archivo HTML no encontrado: {html_file}")

    # Subir el Audio
    if os.path.exists(audio_file):
        # Renombrar el audio para que sea más descriptivo en Drive
        audio_drive_name = audio_file.replace('.mp3', f'_{datetime.now().strftime("%Y%m%d")}.mp3')
        upload_file_to_drive(service, audio_drive_name, audio_file, audio_mime)
    else:
        print(f"⚠️ Archivo de audio no encontrado: {audio_file}")

# Import datetime aquí para que funcione el renombrado
from datetime import datetime

if __name__ == '__main__':
    # Ejemplo de uso
    upload_daily_document('index.html', 'resumen_ia.mp3')