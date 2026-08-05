# main.py
import os
import json
import shutil
import hashlib
import io
from datetime import datetime, timedelta
from googleapiclient.http import MediaIoBaseDownload
from youtube_fetcher import fetch_all_youtube_content
from news_fetcher import get_top_news
from summary_generator import generate_summary
from audio_generator import generate_audio
from document_generator import generate_html_document
from drive_uploader import upload_daily_document, upload_file_to_drive, authenticate_drive, download_history_from_drive

# --- CONFIGURACIÓN ---
HISTORY_FOLDER = "historial"
MAX_HISTORY_DAYS = 10
TOP_NEWS_LIMIT = 15
MAX_NEWS_TOTAL = 10
MIN_NEWS_TOTAL = 7
PARENT_FOLDER_ID = os.environ.get('PARENT_FOLDER_ID')
# --------------------

def ensure_history_folder():
    if not os.path.exists(HISTORY_FOLDER):
        os.makedirs(HISTORY_FOLDER)
        print(f"✅ Carpeta '{HISTORY_FOLDER}' creada.")

def get_daily_filename(base_name, extension):
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{base_name}_{date_str}.{extension}"

def cleanup_old_history():
    if not os.path.exists(HISTORY_FOLDER):
        return
    
    html_files = []
    for filename in os.listdir(HISTORY_FOLDER):
        if filename.startswith("resumen_") and filename.endswith(".html"):
            try:
                date_str = filename.replace("resumen_", "").replace(".html", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                html_files.append((file_date, filename))
            except ValueError:
                print(f"⚠️ Archivo con formato no reconocido: {filename}")
                continue
    
    html_files.sort(key=lambda x: x[0], reverse=True)
    
    if len(html_files) > MAX_HISTORY_DAYS:
        for _, filename in html_files[MAX_HISTORY_DAYS:]:
            file_path = os.path.join(HISTORY_FOLDER, filename)
            try:
                os.remove(file_path)
                print(f"🗑️ Eliminado histórico antiguo: {filename}")
                audio_file = file_path.replace(".html", ".mp3")
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                    print(f"🗑️ Eliminado audio asociado: {os.path.basename(audio_file)}")
            except Exception as e:
                print(f"⚠️ Error al eliminar {filename}: {e}")
    else:
        print(f"✅ Historial dentro del límite ({len(html_files)}/{MAX_HISTORY_DAYS} días)")

def generate_no_news_document():
    date_str = datetime.now().strftime("%Y-%m-%d")
    summary_data = {
        "summary": f"No se encontraron noticias relevantes en las fuentes monitoreadas el día {date_str}.",
        "news": []
    }
    
    html_filename = get_daily_filename("resumen", "html")
    html_file = generate_html_document(
        summary_data, 
        "audio_no_disponible.mp3",
        html_filename
    )
    
    ensure_history_folder()
    html_path = os.path.join(HISTORY_FOLDER, html_file)
    shutil.move(html_file, html_path)
    print(f"✅ Documento 'sin novedades' guardado en {html_path}")
    
    return html_file

def run_agent():
    print(f"\n{'='*60}")
    print(f"🤖 INICIANDO AGENTE IA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"📊 Configuración: Mínimo {MIN_NEWS_TOTAL} noticias, Máximo {MAX_NEWS_TOTAL}")

    if not os.environ.get('YOUTUBE_API_KEY'):
        print("❌ ERROR: YOUTUBE_API_KEY no está configurada.")
        return False
    
    if not os.environ.get('DEEPSEEK_API_KEY'):
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada.")
        return False

    ensure_history_folder()

    print("\n📹 PASO 1: Obteniendo contenido de YouTube...")
    youtube_videos = []
    try:
        youtube_videos = fetch_all_youtube_content()
        if not youtube_videos:
            print("⚠️ No se encontraron videos nuevos en YouTube.")
        else:
            print(f"✅ Se encontraron {len(youtube_videos)} videos con transcripción")
            canales = set()
            for v in youtube_videos:
                canal = v.get('channel', 'Desconocido')
                canales.add(canal)
            print(f"   Canales: {', '.join(canales)}")
    except Exception as e:
        print(f"⚠️ Error al obtener contenido de YouTube: {e}")

    print("\n📰 PASO 1.5: Obteniendo noticias de fuentes externas...")
    external_news = []
    try:
        external_news = get_top_news(limit=TOP_NEWS_LIMIT)
        if not external_news:
            print("⚠️ No se encontraron noticias en fuentes externas.")
        else:
            print(f"✅ Se seleccionaron {len(external_news)} noticias relevantes.")
    except Exception as e:
        print(f"⚠️ Error al obtener noticias externas: {e}")

    print("\n🧠 PASO 2: Generando resumen combinado con DeepSeek...")
    
    total_available = len(youtube_videos) + len(external_news)
    if total_available < MIN_NEWS_TOTAL:
        print(f"⚠️ Solo hay {total_available} noticias disponibles. Se necesita al menos {MIN_NEWS_TOTAL}.")
        if len(external_news) < MIN_NEWS_TOTAL:
            print("🔄 Intentando obtener más noticias externas...")
            additional_news = get_top_news(limit=TOP_NEWS_LIMIT * 2)
            if additional_news:
                existing_titles = [item.get('title') for item in external_news]
                for article in additional_news:
                    if article.get('title') not in existing_titles:
                        external_news.append(article)
                        existing_titles.append(article.get('title'))
                print(f"✅ Total de noticias externas ahora: {len(external_news)}")
    
    if not youtube_videos and not external_news:
        print("❌ No se encontraron noticias de ninguna fuente. Generando documento 'sin novedades'...")
        generate_no_news_document()
        print("✅ Documento 'sin novedades' generado (index.html no se modificó).")
        return True

    combined_news = []
    
    # --- LIMITAR NOTICIAS DE YOUTUBE A 3 (una por canal) ---
    youtube_limited = youtube_videos[:3]
    
    for video in youtube_limited:
        combined_news.append({
            'title': video.get('title', 'Sin título'),
            'resumen': video.get('transcript', '')[:300] if video.get('transcript') else 'Transcripción no disponible',
            'fuente': f"YouTube: {video.get('channel', 'Desconocido')}",
            'url': video.get('url', '#'),
            'tipo': 'youtube'
        })
    
    for article in external_news:
        combined_news.append({
            'title': article.get('title', 'Sin título'),
            'resumen': article.get('summary', '')[:300],
            'fuente': article.get('source', 'Fuente desconocida'),
            'url': article.get('link', '#'),
            'tipo': 'externo'
        })
    
    print(f"📊 Total de noticias para resumen: {len(combined_news)}")
    print(f"   🎥 YouTube: {len(youtube_limited)} noticias")
    print(f"   📰 Externas: {len(combined_news) - len(youtube_limited)} noticias")

    try:
        summary_data = generate_summary(combined_news)
        if not summary_data or not summary_data.get('summary'):
            print("❌ No se pudo generar el resumen. Se mantendrá el índice anterior.")
            return False
        
        print(f"✅ Resumen generado: {summary_data['summary'][:100]}...")
        print(f"   📰 {len(summary_data.get('news', []))} noticias extraídas")
        
    except Exception as e:
        print(f"❌ Error al generar resumen: {e}")
        print("⚠️ Se mantendrá el índice anterior sin cambios.")
        return False

    # --- PASO 3: Generar audio ---
    print("\n🎧 PASO 3: Generando audio...")
    audio_filename = get_daily_filename("resumen", "mp3")
    audio_file = None
    try:
        summary_text = summary_data.get('summary', '')
        audio_file = generate_audio(summary_text, audio_filename)
        if audio_file and os.path.exists(audio_file):
            print(f"✅ Audio generado: {audio_file}")
        else:
            print("⚠️ No se pudo generar el audio, continuando sin él")
            audio_file = None
    except Exception as e:
        print(f"⚠️ Error al generar audio: {e}")
        audio_file = None

    # --- PASO 4: Generar documento HTML con fecha ---
    print("\n📄 PASO 4: Generando documento HTML con fecha...")
    html_filename = get_daily_filename("resumen", "html")
    try:
        html_file = generate_html_document(
            summary_data, 
            "resumen_ia.mp3",
            html_filename
        )
        print(f"✅ Documento HTML generado: {html_file}")
    except Exception as e:
        print(f"❌ Error al generar HTML: {e}")
        return False

    # --- PASO 5: Mover archivos a histórico ---
    print("\n📁 PASO 5: Archivando en histórico...")
    try:
        ensure_history_folder()
        html_path = os.path.join(HISTORY_FOLDER, html_file)
        shutil.move(html_file, html_path)
        print(f"✅ HTML movido a {html_path}")
        
        if audio_file and os.path.exists(audio_file):
            audio_path = os.path.join(HISTORY_FOLDER, audio_file)
            shutil.move(audio_file, audio_path)
            print(f"✅ Audio movido a {audio_path}")
    except Exception as e:
        print(f"⚠️ Error al mover archivos: {e}")

    # --- PASO 6: Copiar el HTML más reciente como 'index.html' ---
    print("\n🌐 PASO 6: Preparando index.html para GitHub Pages...")
    try:
        latest_html = os.path.join(HISTORY_FOLDER, html_file)
        shutil.copy(latest_html, "index.html")
        print(f"✅ index.html actualizado con el resumen del día.")
        
        if audio_file and os.path.exists(os.path.join(HISTORY_FOLDER, audio_file)):
            shutil.copy(os.path.join(HISTORY_FOLDER, audio_file), "resumen_ia.mp3")
            print(f"✅ resumen_ia.mp3 actualizado.")
        else:
            if os.path.exists("resumen_ia.mp3"):
                os.remove("resumen_ia.mp3")
                print("🗑️ Eliminado resumen_ia.mp3 antiguo (no hay audio nuevo)")
    except Exception as e:
        print(f"⚠️ Error al copiar archivos: {e}")

    # --- PASO 7: Limpiar histórico ---
    print(f"\n🗑️ PASO 7: Limpiando histórico (manteniendo {MAX_HISTORY_DAYS} días)...")
    cleanup_old_history()

    # --- PASO 8: Subir a Google Drive ---
    if os.environ.get('PARENT_FOLDER_ID'):
        print("\n☁️ PASO 8: Subiendo archivos a Google Drive...")
        try:
            upload_daily_document(
                os.path.join(HISTORY_FOLDER, html_file), 
                os.path.join(HISTORY_FOLDER, audio_file) if audio_file else None
            )
            
            print("   Subiendo archivos principales (index.html y resumen_ia.mp3)...")
            service = authenticate_drive()
            if service:
                if os.path.exists("index.html"):
                    upload_file_to_drive(service, "index.html", "index.html", "text/html")
                if os.path.exists("resumen_ia.mp3"):
                    upload_file_to_drive(service, "resumen_ia.mp3", "resumen_ia.mp3", "audio/mpeg")
            else:
                print("⚠️ No se pudo autenticar con Drive para subir archivos principales")
            
            print("✅ Archivos subidos a Drive")
        except Exception as e:
            print(f"⚠️ Error al subir a Drive: {e}")
    else:
        print("\n⚠️ PARENT_FOLDER_ID no configurada. Omitiendo subida a Drive.")

    # --- PASO 9: DESCARGAR HISTÓRICOS DESDE DRIVE Y ACTUALIZAR index.html (MEJORADO) ---
    print("\n🔄 PASO 9: Sincronizando históricos desde Google Drive...")
    try:
        service = authenticate_drive()
        if service:
            # Buscar archivos HTML históricos en Drive (excluir resumen_ia.mp3)
            query = "name contains 'resumen_' and name contains '.html' and trashed=false"
            if PARENT_FOLDER_ID:
                query += f" and '{PARENT_FOLDER_ID}' in parents"
            
            results = service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                pageSize=100
            ).execute()
            files = results.get('files', [])
            print(f"📁 Encontrados {len(files)} archivos HTML en Drive.")
            
            if files:
                os.makedirs(HISTORY_FOLDER, exist_ok=True)
                downloaded_count = 0
                for file in files:
                    filename = file['name']
                    # Saltar archivos que no sean HTML históricos
                    if not filename.startswith('resumen_') or not filename.endswith('.html'):
                        continue
                    filepath = os.path.join(HISTORY_FOLDER, filename)
                    # --- FORZAR DESCARGA: sobrescribir siempre ---
                    print(f"📥 Descargando: {filename} (sobrescribiendo)")
                    request = service.files().get_media(fileId=file['id'])
                    fh = io.FileIO(filepath, 'wb')
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    print(f"✅ Descargado: {filename}")
                    downloaded_count += 1
                print(f"✅ {downloaded_count} archivos HTML descargados desde Drive.")
            else:
                print("ℹ️ No hay archivos HTML históricos en Drive.")
        
        # Regenerar index.html con los históricos actualizados
        print("\n📄 Regenerando index.html con los históricos actualizados...")
        updated_html = generate_html_document(
            summary_data, 
            "resumen_ia.mp3",
            "index.html"
        )
        print(f"✅ index.html regenerado con históricos incluidos.")
        
        # Asegurar consistencia copiando desde histórico
        if os.path.exists(os.path.join(HISTORY_FOLDER, html_file)):
            shutil.copy(os.path.join(HISTORY_FOLDER, html_file), "index.html")
            print(f"✅ index.html copiado desde histórico para asegurar consistencia.")
            
    except Exception as e:
        print(f"⚠️ Error al sincronizar históricos: {e}")

    print("\n" + "="*60)
    print("✅ AGENTE COMPLETADO CON ÉXITO")
    print(f"📊 Resumen del día: {summary_data.get('summary', '')[:200]}...")
    print(f"📁 Archivos generados:")
    print(f"   - {HISTORY_FOLDER}/{html_file}")
    if audio_file:
        print(f"   - {HISTORY_FOLDER}/{audio_file}")
    print(f"   - index.html (copia más reciente)")
    if os.path.exists("resumen_ia.mp3"):
        print(f"   - resumen_ia.mp3 (copia más reciente)")
    print(f"📅 Historial: {MAX_HISTORY_DAYS} días disponibles.")
    print(f"📰 Fuentes: YouTube ({len(youtube_limited)}) + {len(external_news)} externas.")
    print(f"📋 Total de noticias en el resumen: {len(summary_data.get('news', []))}")
    print("="*60)
    
    return True

def run_agent_with_retry(max_retries=2):
    import time
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n🔄 Reintento {attempt} de {max_retries}...")
            time.sleep(30)
        if run_agent():
            return True
    print("\n❌ El agente falló después de todos los reintentos.")
    return False

if __name__ == '__main__':
    import sys
    print("🚀 AGENTE DE INTELIGENCIA ARTIFICIAL - EBS")
    print(f"📅 Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    ensure_history_folder()
    success = run_agent_with_retry()
    sys.exit(0 if success else 1)