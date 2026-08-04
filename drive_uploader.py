# drive_uploader.py
import os
import pickle
import time
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io

# --- CONFIGURACIÓN ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
PARENT_FOLDER_ID = os.environ.get('PARENT_FOLDER_ID')
MAX_RETRIES = 3
# ---------------------

def authenticate_drive():
    """Autentica con Google Drive y devuelve el servicio."""
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'
    
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            print("✅ Credenciales cargadas desde token.json")
            if creds and creds.valid:
                print("✅ Credenciales válidas")
                return build('drive', 'v3', credentials=creds)
            elif creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("✅ Token refrescado correctamente")
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                    return build('drive', 'v3', credentials=creds)
                except Exception as e:
                    print(f"⚠️ Error al refrescar token: {e}")
                    os.remove(token_file)
                    print("🗑️ token.json eliminado para forzar nueva autenticación")
            else:
                print("⚠️ Credenciales inválidas, se eliminará token.json")
                os.remove(token_file)
        except Exception as e:
            print(f"⚠️ Error al cargar token.json: {e}")
            if os.path.exists(token_file):
                os.remove(token_file)
    
    if not os.path.exists(credentials_file):
        print(f"❌ Error: No se encuentra el archivo '{credentials_file}'.")
        return None
    
    try:
        print("🔐 Iniciando flujo de autenticación OAuth...")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        try:
            print("   Intentando autenticación sin navegador (headless)...")
            creds = flow.run_console()
            print("✅ Autenticación headless exitosa")
        except Exception as e:
            print(f"⚠️ Error en autenticación headless: {e}")
            print("   Intentando autenticación con navegador...")
            creds = flow.run_local_server(port=0)
            print("✅ Autenticación con navegador exitosa")
        
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        print(f"✅ Credenciales guardadas en {token_file}")
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error en el flujo OAuth: {e}")
        return None

def upload_file_to_drive(service, filename, filepath, mime_type, retry_count=0):
    """Sube un archivo a Google Drive con reintentos."""
    if not service:
        print("❌ Servicio de Drive no disponible.")
        return None
    if not os.path.exists(filepath):
        print(f"⚠️ Archivo no encontrado: {filepath}")
        return None
    
    try:
        file_metadata = {'name': filename}
        if PARENT_FOLDER_ID:
            file_metadata['parents'] = [PARENT_FOLDER_ID]
            print(f"📁 Subiendo a carpeta con ID: {PARENT_FOLDER_ID}")
        else:
            print(f"📁 Subiendo a la raíz de Drive")
        
        media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()
        file_id = file.get('id')
        print(f"✅ Archivo subido a Drive: {filename} (ID: {file_id})")
        return file_id
    except HttpError as error:
        if error.resp.status in [429, 500, 503] and retry_count < MAX_RETRIES:
            wait_time = (retry_count + 1) * 5
            print(f"⏳ Reintentando en {wait_time} segundos...")
            time.sleep(wait_time)
            return upload_file_to_drive(service, filename, filepath, mime_type, retry_count + 1)
        print(f"❌ Error al subir {filename}: {error}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado al subir {filename}: {e}")
        return None

def make_file_public(service, file_id):
    """Hace que un archivo sea público."""
    if not service or not file_id:
        return False
    try:
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file_id, body=permission, fields='id').execute()
        print(f"   🔓 Archivo {file_id} configurado como público")
        return True
    except HttpError as error:
        print(f"⚠️ Error al hacer público el archivo {file_id}: {error}")
        return False

def upload_daily_document(html_file, audio_file=None):
    """Sube los archivos del día a Google Drive."""
    print("\n☁️ Iniciando subida a Google Drive...")
    service = authenticate_drive()
    if not service:
        print("❌ No se pudo autenticar con Google Drive.")
        return None
    
    results = {}
    if html_file and os.path.exists(html_file):
        filename = os.path.basename(html_file)
        file_id = upload_file_to_drive(service, filename, html_file, 'text/html')
        if file_id:
            results['html'] = {'id': file_id, 'name': filename}
            make_file_public(service, file_id)
    
    if audio_file and os.path.exists(audio_file):
        filename = os.path.basename(audio_file)
        file_id = upload_file_to_drive(service, filename, audio_file, 'audio/mpeg')
        if file_id:
            results['audio'] = {'id': file_id, 'name': filename}
            make_file_public(service, file_id)
    
    return results if results else None

def download_history_from_drive(history_folder="historial"):
    """
    Descarga todos los archivos históricos (resumen_*.html y *.mp3) desde Drive.
    """
    print("\n📥 Descargando históricos desde Google Drive...")
    service = authenticate_drive()
    if not service:
        print("❌ No se pudo autenticar con Google Drive.")
        return False
    
    # Buscar archivos en la carpeta raíz de Drive (o en la carpeta especificada)
    query = "name contains 'resumen_' and (mimeType='text/html' or mimeType='audio/mpeg') and trashed=false"
    if PARENT_FOLDER_ID:
        query += f" and '{PARENT_FOLDER_ID}' in parents"
    
    try:
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=100
        ).execute()
        files = results.get('files', [])
        print(f"📁 Encontrados {len(files)} archivos en Drive.")
        
        if not files:
            print("ℹ️ No hay archivos históricos en Drive para descargar.")
            return True
        
        # Crear carpeta historial local
        os.makedirs(history_folder, exist_ok=True)
        
        downloaded_count = 0
        for file in files:
            file_id = file['id']
            filename = file['name']
            filepath = os.path.join(history_folder, filename)
            
            # Saltar si el archivo ya existe localmente
            if os.path.exists(filepath):
                print(f"⏭️ {filename} ya existe localmente, saltando.")
                continue
            
            print(f"📥 Descargando: {filename}")
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(filepath, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"   Progreso: {int(status.progress() * 100)}%")
            print(f"✅ Descargado: {filename}")
            downloaded_count += 1
        
        print(f"✅ {downloaded_count} archivos descargados a {history_folder}/")
        return True
        
    except HttpError as error:
        print(f"❌ Error al listar archivos en Drive: {error}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def upload_history_folder(history_folder="historial", max_files=10):
    """Sube los archivos más recientes del histórico a Drive."""
    if not os.path.exists(history_folder):
        print(f"⚠️ Carpeta '{history_folder}' no encontrada.")
        return []
    
    html_files = []
    for f in os.listdir(history_folder):
        if f.startswith("resumen_") and f.endswith(".html"):
            try:
                date_str = f.replace("resumen_", "").replace(".html", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                html_files.append((file_date, f))
            except ValueError:
                continue
    
    html_files.sort(key=lambda x: x[0], reverse=True)
    files_to_upload = html_files[:max_files]
    
    if not files_to_upload:
        print("ℹ️ No hay archivos en el histórico para subir.")
        return []
    
    service = authenticate_drive()
    if not service:
        return []
    
    uploaded = []
    for _, filename in files_to_upload:
        filepath = os.path.join(history_folder, filename)
        file_id = upload_file_to_drive(service, filename, filepath, 'text/html')
        if file_id:
            uploaded.append(filename)
            audio_file = filepath.replace(".html", ".mp3")
            if os.path.exists(audio_file):
                audio_name = os.path.basename(audio_file)
                upload_file_to_drive(service, audio_name, audio_file, 'audio/mpeg')
    
    return uploaded

# --- Función para pruebas ---
if __name__ == '__main__':
    print("=== Probando drive_uploader.py ===")
    print("🧪 Probando descarga de históricos desde Drive...")
    download_history_from_drive()