# main.py
import os
import json
import shutil
import hashlib
from datetime import datetime, timedelta
from youtube_fetcher import fetch_all_youtube_content
from news_fetcher import get_top_news
from summary_generator import generate_summary
from audio_generator import generate_audio
from document_generator import generate_html_document
from drive_uploader import upload_daily_document, upload_file_to_drive, authenticate_drive

# --- CONFIGURACIÓN ---
HISTORY_FOLDER = "historial"
MAX_HISTORY_DAYS = 10
TOP_NEWS_LIMIT = 5  # REDUCIDO de 10 a 5
MAX_NEWS_TOTAL = 5   # NUEVO: Límite de noticias para el resumen
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
    """Genera un documento HTML cuando no hay novedades, pero NO sobrescribe el index.html existente."""
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
    
    # No se copia a index.html para preservar el boletín anterior
    # cleanup_old_history() no se ejecuta para no borrar históricos si no hay contenido nuevo
    return html_file

def run_agent():
    print(f"\n{'='*60}")
    print(f"🤖 INICIANDO AGENTE IA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

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
    if not youtube_videos and not external_news:
        print("❌ No se encontraron noticias de ninguna fuente. Generando documento 'sin novedades'...")
        generate_no_news_document()
        print("✅ Documento 'sin novedades' generado (index.html no se modificó).")
        return True

    combined_news = []
    for video in youtube_videos:
        combined_news.append({
            'title': video.get('title', 'Sin título'),
            'resumen': video.get('transcript', '')[:200] if video.get('transcript') else 'Transcripción no disponible',  # REDUCIDO
            'fuente': f"YouTube: {video.get('channel', 'Desconocido')}",
            'url': video.get('url', '#'),
            'tipo': 'youtube'
        })
    
    for article in external_news:
        combined_news.append({
            'title': article.get('title', 'Sin título'),
            'resumen': article.get('summary', '')[:200],  # REDUCIDO
            'fuente': article.get('source', 'Fuente desconocida'),
            'url': article.get('link', '#'),
            'tipo': 'externo'
        })
    
    print(f"📊 Total de noticias para resumen: {len(combined_news)}")

    try:
        summary_data = generate_summary(combined_news)
        if not summary_data or not summary_data.get('summary'):
            print("❌ No se pudo generar el resumen. Se mantendrá el índice anterior.")
            return False  # Salir sin actualizar index.html ni historial
        
        print(f"✅ Resumen generado: {summary_data['summary'][:100]}...")
        print(f"   📰 {len(summary_data.get('news', []))} noticias extraídas")
        
        # --- FORZAR INCLUSIÓN DE NOTICIAS DE YOUTUBE ---
        youtube_news_in_summary = [item for item in summary_data.get('news', []) if item.get('tipo') == 'youtube']
        if len(youtube_news_in_summary) < len(youtube_videos):
            print(f"⚠️ Faltan noticias de YouTube en el resumen. Añadiendo manualmente...")
            existing_titles = [item.get('title') for item in summary_data.get('news', [])]
            for video in youtube_videos:
                if video.get('title') not in existing_titles:
                    summary_data['news'].append({
                        'title': video.get('title', 'Sin título'),
                        'resumen': 'Noticia destacada del día desde YouTube.',
                        'fuente': f"YouTube: {video.get('channel', 'Desconocido')}",
                        'url': video.get('url', '#'),
                        'tipo': 'youtube'
                    })
                    print(f"✅ Añadida noticia de YouTube: {video.get('title')}")
        # --- FIN DE LA ADICIÓN ---
        
    except Exception as e:
        print(f"❌ Error al generar resumen: {e}")
        print("⚠️ Se mantendrá el índice anterior sin cambios.")
        return False

    # --- Solo se ejecuta si el resumen se generó correctamente ---
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

    print("\n📁 PASO 5: Archivando en histórico...")
    try:
        html_path = os.path.join(HISTORY_FOLDER, html_file)
        shutil.move(html_file, html_path)
        print(f"✅ HTML movido a {html_path}")
        
        if audio_file and os.path.exists(audio_file):
            audio_path = os.path.join(HISTORY_FOLDER, audio_file)
            shutil.move(audio_file, audio_path)
            print(f"✅ Audio movido a {audio_path}")
    except Exception as e:
        print(f"⚠️ Error al mover archivos: {e}")

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

    print(f"\n🗑️ PASO 7: Limpiando histórico (manteniendo {MAX_HISTORY_DAYS} días)...")
    cleanup_old_history()

    # --- PASO 8: Subir a Google Drive (mejorado) ---
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
    print(f"📰 Fuentes: YouTube + {len(external_news)} fuentes externas.")
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