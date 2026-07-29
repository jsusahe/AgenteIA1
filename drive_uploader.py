# drive_uploader.py
import os
import pickle
import time
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# --- CONFIGURACIÓN ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']  # Permisos para crear archivos
PARENT_FOLDER_ID = os.environ.get('PARENT_FOLDER_ID')    # ID de carpeta en Drive (opcional)
MAX_RETRIES = 3  # Número de reintentos en caso de error
# ---------------------

def authenticate_drive():
    """
    Autentica con Google Drive y devuelve el servicio.
    En entornos headless (GitHub Actions), usa autenticación sin navegador.
    """
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'
    
    # 1. Intentar cargar credenciales existentes
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            print("✅ Credenciales cargadas desde token.json")
            
            # Verificar si las credenciales son válidas
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
                    # Si falla el refresco, eliminar token.json para forzar nueva autenticación
                    os.remove(token_file)
                    print("🗑️ token.json eliminado para forzar nueva autenticación")
            else:
                print("⚠️ Credenciales inválidas, se eliminará token.json")
                os.remove(token_file)
        except Exception as e:
            print(f"⚠️ Error al cargar token.json: {e}")
            if os.path.exists(token_file):
                os.remove(token_file)
    
    # 2. Si no hay credenciales válidas, iniciar flujo OAuth
    if not os.path.exists(credentials_file):
        print(f"❌ Error: No se encuentra el archivo '{credentials_file}'.")
        print("   Descárgalo de Google Cloud Console y colócalo en la raíz del proyecto.")
        return None
    
    try:
        print("🔐 Iniciando flujo de autenticación OAuth...")
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        
        # Intentar autenticación sin navegador (headless) primero
        try:
            print("   Intentando autenticación sin navegador (headless)...")
            creds = flow.run_console()
            print("✅ Autenticación headless exitosa")
        except Exception as e:
            print(f"⚠️ Error en autenticación headless: {e}")
            print("   Intentando autenticación con navegador (solo funciona localmente)...")
            try:
                creds = flow.run_local_server(port=0)
                print("✅ Autenticación con navegador exitosa")
            except Exception as e2:
                print(f"❌ Error en autenticación con navegador: {e2}")
                print("\n   🔑 Para resolver esto manualmente, puedes:")
                print("   1. Ejecutar el script localmente (con navegador) para generar token.json.")
                print("   2. Luego subir token.json como secreto en GitHub Actions.")
                print("   3. O usar una cuenta de servicio (más complejo, pero más seguro).")
                return None
        
        # Guardar las credenciales para la próxima ejecución
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        print(f"✅ Credenciales guardadas en {token_file}")
        
        return build('drive', 'v3', credentials=creds)
        
    except Exception as e:
        print(f"❌ Error en el flujo OAuth: {e}")
        return None

def upload_file_to_drive(service, filename, filepath, mime_type, retry_count=0):
    """
    Sube un archivo a Google Drive con reintentos en caso de error.
    
    Args:
        service: Servicio de Google Drive autenticado.
        filename (str): Nombre del archivo en Drive.
        filepath (str): Ruta local del archivo.
        mime_type (str): Tipo MIME del archivo.
        retry_count (int): Número de reintentos actual.
    
    Returns:
        str: ID del archivo subido, o None si falla.
    """
    if not service:
        print("❌ Servicio de Drive no disponible.")
        return None
    
    if not os.path.exists(filepath):
        print(f"⚠️ Archivo no encontrado: {filepath}")
        return None
    
    try:
        # Preparar metadatos del archivo
        file_metadata = {'name': filename}
        if PARENT_FOLDER_ID:
            file_metadata['parents'] = [PARENT_FOLDER_ID]
            print(f"📁 Subiendo a carpeta con ID: {PARENT_FOLDER_ID}")
        else:
            print(f"📁 Subiendo a la raíz de Drive (PARENT_FOLDER_ID no configurado)")
        
        # Preparar el archivo para subir
        media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)
        
        # Ejecutar la subida
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()
        
        file_id = file.get('id')
        web_link = file.get('webViewLink', 'No disponible')
        
        print(f"✅ Archivo subido a Drive: {filename}")
        print(f"   📎 ID: {file_id}")
        print(f"   🔗 Enlace: {web_link}")
        
        return file_id
        
    except HttpError as error:
        print(f"❌ Error HTTP al subir {filename}: {error}")
        
        # Reintentar si el error es transitorio (503, 429, 500)
        if error.resp.status in [429, 500, 503] and retry_count < MAX_RETRIES:
            wait_time = (retry_count + 1) * 5  # 5, 10, 15 segundos
            print(f"⏳ Reintentando en {wait_time} segundos... (Intento {retry_count + 1}/{MAX_RETRIES})")
            time.sleep(wait_time)
            return upload_file_to_drive(service, filename, filepath, mime_type, retry_count + 1)
        
        return None
        
    except Exception as e:
        print(f"❌ Error inesperado al subir {filename}: {e}")
        return None

def make_file_public(service, file_id):
    """
    Hace que un archivo sea público (cualquier persona con el enlace puede verlo).
    
    Args:
        service: Servicio de Google Drive autenticado.
        file_id (str): ID del archivo en Drive.
    
    Returns:
        bool: True si se configuró correctamente, False en caso contrario.
    """
    if not service or not file_id:
        return False
    
    try:
        # Crear un permiso de lectura para cualquier persona
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission,
            fields='id'
        ).execute()
        
        print(f"   🔓 Archivo {file_id} configurado como público")
        return True
        
    except HttpError as error:
        print(f"⚠️ Error al hacer público el archivo {file_id}: {error}")
        return False

def upload_daily_document(html_file, audio_file=None):
    """
    Función principal para subir los archivos del día a Google Drive.
    
    Args:
        html_file (str): Ruta al archivo HTML.
        audio_file (str): Ruta al archivo de audio (opcional).
    
    Returns:
        dict: Diccionario con los IDs de los archivos subidos.
    """
    print("\n☁️ Iniciando subida a Google Drive...")
    
    # Autenticar
    service = authenticate_drive()
    if not service:
        print("❌ No se pudo autenticar con Google Drive.")
        return None
    
    results = {}
    
    # --- Subir HTML ---
    if html_file and os.path.exists(html_file):
        print(f"\n📄 Subiendo HTML: {html_file}")
        filename = os.path.basename(html_file)
        file_id = upload_file_to_drive(service, filename, html_file, 'text/html')
        
        if file_id:
            results['html'] = {'id': file_id, 'name': filename}
            # Opcional: Hacer público el archivo HTML
            make_file_public(service, file_id)
    else:
        print(f"⚠️ Archivo HTML no encontrado: {html_file}")
    
    # --- Subir Audio ---
    if audio_file and os.path.exists(audio_file):
        print(f"\n🎧 Subiendo audio: {audio_file}")
        filename = os.path.basename(audio_file)
        file_id = upload_file_to_drive(service, filename, audio_file, 'audio/mpeg')
        
        if file_id:
            results['audio'] = {'id': file_id, 'name': filename}
            # Opcional: Hacer público el archivo de audio
            make_file_public(service, file_id)
    else:
        print(f"ℹ️ Archivo de audio no encontrado o no especificado: {audio_file}")
    
    # --- Resumen de la subida ---
    if results:
        print(f"\n✅ Subida completada. {len(results)} archivo(s) subido(s).")
        for key, value in results.items():
            print(f"   📎 {key}: {value['name']} (ID: {value['id']})")
    else:
        print("\n❌ No se subió ningún archivo.")
    
    return results if results else None

def upload_history_folder(history_folder="historial", max_files=10):
    """
    Sube los archivos más recientes de la carpeta de histórico a Drive.
    Útil para mantener una copia de seguridad del histórico en Drive.
    
    Args:
        history_folder (str): Carpeta donde se guarda el histórico local.
        max_files (int): Número máximo de archivos recientes a subir.
    
    Returns:
        list: Lista de archivos subidos exitosamente.
    """
    if not os.path.exists(history_folder):
        print(f"⚠️ Carpeta '{history_folder}' no encontrada.")
        return []
    
    # Obtener archivos HTML del histórico (ordenados por fecha)
    html_files = []
    for f in os.listdir(history_folder):
        if f.startswith("resumen_") and f.endswith(".html"):
            try:
                date_str = f.replace("resumen_", "").replace(".html", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                html_files.append((file_date, f))
            except ValueError:
                continue
    
    # Ordenar por fecha (más reciente primero)
    html_files.sort(key=lambda x: x[0], reverse=True)
    
    # Tomar solo los más recientes (según max_files)
    files_to_upload = html_files[:max_files]
    
    if not files_to_upload:
        print("ℹ️ No hay archivos HTML en el histórico para subir.")
        return []
    
    print(f"📁 Subiendo {len(files_to_upload)} archivos del histórico a Drive...")
    
    # Autenticar
    service = authenticate_drive()
    if not service:
        print("❌ No se pudo autenticar con Google Drive.")
        return []
    
    uploaded = []
    
    for _, filename in files_to_upload:
        filepath = os.path.join(history_folder, filename)
        file_id = upload_file_to_drive(service, filename, filepath, 'text/html')
        
        if file_id:
            uploaded.append(filename)
            # También subir el audio asociado si existe
            audio_file = filepath.replace(".html", ".mp3")
            if os.path.exists(audio_file):
                audio_name = os.path.basename(audio_file)
                upload_file_to_drive(service, audio_name, audio_file, 'audio/mpeg')
    
    print(f"✅ {len(uploaded)} archivos del histórico subidos a Drive.")
    return uploaded

# --- Función para pruebas ---
if __name__ == '__main__':
    print("=== Probando drive_uploader.py ===")
    print(f"📁 PARENT_FOLDER_ID: {PARENT_FOLDER_ID if PARENT_FOLDER_ID else 'No configurado (se usará raíz)'}")
    
    # Prueba 1: Verificar autenticación
    print("\n🔐 Prueba de autenticación...")
    service = authenticate_drive()
    if service:
        print("✅ Autenticación exitosa")
        
        # Prueba 2: Subir un archivo de prueba
        print("\n📤 Prueba de subida...")
        test_content = "<h1>Prueba de subida a Google Drive</h1><p>Este es un archivo de prueba generado por drive_uploader.py</p>"
        test_file = "test_drive_upload.html"
        
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        file_id = upload_file_to_drive(service, "test_drive_upload.html", test_file, "text/html")
        if file_id:
            print(f"✅ Archivo de prueba subido con ID: {file_id}")
            # Hacer público el archivo de prueba
            make_file_public(service, file_id)
            print(f"🔗 Enlace público: https://drive.google.com/file/d/{file_id}/view")
        else:
            print("❌ Error al subir archivo de prueba")
        
        # Limpiar archivo de prueba
        if os.path.exists(test_file):
            os.remove(test_file)
            print("🧹 Archivo de prueba eliminado")
        
        # Prueba 3: Subir histórico (si existe)
        print("\n📂 Prueba de subida de histórico...")
        if os.path.exists("historial"):
            upload_history_folder("historial", max_files=3)
        else:
            print("ℹ️ Carpeta 'historial' no encontrada. Omitiendo prueba.")
    
    else:
        print("❌ Error de autenticación")
    
    print("\n✅ Pruebas completadas")