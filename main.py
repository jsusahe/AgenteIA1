# main.py
import os
import json
import shutil
from datetime import datetime, timedelta
from youtube_fetcher import fetch_all_youtube_content
from summary_generator import generate_summary
from audio_generator import generate_audio
from document_generator import generate_html_document
from drive_uploader import upload_daily_document

# --- CONFIGURACIÓN ---
HISTORY_FOLDER = "historial"          # Carpeta donde se guarda el histórico
MAX_HISTORY_DAYS = 10                 # Número máximo de días a mantener
# --------------------

def ensure_history_folder():
    """Crea la carpeta de histórico si no existe."""
    if not os.path.exists(HISTORY_FOLDER):
        os.makedirs(HISTORY_FOLDER)
        print(f"✅ Carpeta '{HISTORY_FOLDER}' creada.")

def get_daily_filename(base_name, extension):
    """Genera un nombre de archivo con la fecha actual."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{base_name}_{date_str}.{extension}"

def cleanup_old_history():
    """
    Elimina archivos de histórico más antiguos que MAX_HISTORY_DAYS.
    Mantiene solo los últimos N días (por fecha en el nombre del archivo).
    """
    if not os.path.exists(HISTORY_FOLDER):
        return
    
    # Obtener lista de archivos HTML en el histórico con su fecha
    html_files = []
    for filename in os.listdir(HISTORY_FOLDER):
        if filename.startswith("resumen_") and filename.endswith(".html"):
            try:
                # Extraer fecha del nombre: resumen_YYYY-MM-DD.html
                date_str = filename.replace("resumen_", "").replace(".html", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                html_files.append((file_date, filename))
            except ValueError:
                # Si no se puede parsear la fecha, ignorar el archivo
                print(f"⚠️ Archivo con formato no reconocido: {filename}")
                continue
    
    # Ordenar por fecha (más reciente primero)
    html_files.sort(key=lambda x: x[0], reverse=True)
    
    # Eliminar los que excedan el límite
    if len(html_files) > MAX_HISTORY_DAYS:
        for _, filename in html_files[MAX_HISTORY_DAYS:]:
            file_path = os.path.join(HISTORY_FOLDER, filename)
            try:
                os.remove(file_path)
                print(f"🗑️ Eliminado histórico antiguo: {filename}")
                # También eliminar el audio asociado si existe
                audio_file = file_path.replace(".html", ".mp3")
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                    print(f"🗑️ Eliminado audio asociado: {os.path.basename(audio_file)}")
            except Exception as e:
                print(f"⚠️ Error al eliminar {filename}: {e}")
    else:
        print(f"✅ Historial dentro del límite ({len(html_files)}/{MAX_HISTORY_DAYS} días)")

def generate_no_news_document():
    """Genera un documento HTML cuando no hay novedades."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    summary_data = {
        "summary": f"No se encontraron videos nuevos en los canales monitoreados el día {date_str}.",
        "news": []
    }
    
    # Generar HTML con fecha
    html_filename = get_daily_filename("resumen", "html")
    html_file = generate_html_document(
        summary_data, 
        "audio_no_disponible.mp3",
        html_filename
    )
    
    # Mover a histórico
    ensure_history_folder()
    shutil.move(html_file, os.path.join(HISTORY_FOLDER, html_file))
    
    # Copiar como index.html para GitHub Pages
    shutil.copy(os.path.join(HISTORY_FOLDER, html_file), "index.html")
    print(f"✅ index.html actualizado (sin novedades)")
    
    # Limpiar histórico
    cleanup_old_history()
    
    return html_file

def run_agent():
    """Función principal que ejecuta todo el agente."""
    print(f"\n{'='*60}")
    print(f"🤖 INICIANDO AGENTE IA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Verificar variables de entorno
    if not os.environ.get('YOUTUBE_API_KEY'):
        print("❌ ERROR: YOUTUBE_API_KEY no está configurada como variable de entorno.")
        return False
    
    if not os.environ.get('DEEPSEEK_API_KEY'):
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada como variable de entorno.")
        return False

    # Asegurar que existe la carpeta de histórico
    ensure_history_folder()

    # --- PASO 1: Obtener contenido de YouTube ---
    print("\n📹 PASO 1: Obteniendo contenido de YouTube...")
    try:
        videos = fetch_all_youtube_content()
        if not videos:
            print("❌ No se encontraron videos nuevos. Generando documento 'sin novedades'...")
            generate_no_news_document()
            print("✅ Documento 'sin novedades' generado.")
            return True
        print(f"✅ Se encontraron {len(videos)} videos con transcripción")
    except Exception as e:
        print(f"❌ Error al obtener contenido de YouTube: {e}")
        return False

    # --- PASO 2: Generar resumen con DeepSeek ---
    print("\n🧠 PASO 2: Generando resumen con DeepSeek...")
    try:
        summary_data = generate_summary(videos)
        if not summary_data or not summary_data.get('summary'):
            print("❌ No se pudo generar el resumen. Saliendo.")
            return False
        print(f"✅ Resumen generado: {summary_data['summary'][:100]}...")
        print(f"   📰 {len(summary_data.get('news', []))} noticias extraídas")
    except Exception as e:
        print(f"❌ Error al generar resumen: {e}")
        return False

    # --- PASO 3: Generar audio ---
    print("\n🎧 PASO 3: Generando audio...")
    audio_filename = get_daily_filename("resumen", "mp3")
    audio_file = None
    try:
        summary_text = summary_data.get('summary', '')
        audio_file = generate_audio(summary_text, audio_filename)
        if audio_file:
            print(f"✅ Audio generado: {audio_file}")
        else:
            print("⚠️ No se pudo generar el audio, continuando sin él")
    except Exception as e:
        print(f"⚠️ Error al generar audio: {e}")
        print("   Continuando sin audio")

    # --- PASO 4: Generar documento HTML con fecha ---
    print("\n📄 PASO 4: Generando documento HTML...")
    html_filename = get_daily_filename("resumen", "html")
    try:
        html_file = generate_html_document(
            summary_data, 
            audio_file if audio_file else "audio_no_disponible.mp3",
            html_filename
        )
        print(f"✅ Documento HTML generado: {html_file}")
    except Exception as e:
        print(f"❌ Error al generar HTML: {e}")
        return False

    # --- PASO 5: Mover archivos a la carpeta de histórico ---
    print("\n📁 PASO 5: Archivando en histórico...")
    try:
        # Mover HTML al histórico
        html_path = os.path.join(HISTORY_FOLDER, html_file)
        shutil.move(html_file, html_path)
        print(f"✅ HTML movido a {html_path}")
        
        # Mover audio al histórico si existe
        if audio_file and os.path.exists(audio_file):
            audio_path = os.path.join(HISTORY_FOLDER, audio_file)
            shutil.move(audio_file, audio_path)
            print(f"✅ Audio movido a {audio_path}")
    except Exception as e:
        print(f"⚠️ Error al mover archivos: {e}")
        # Intentar continuar aunque falle el movimiento

    # --- PASO 6: Copiar el HTML más reciente como 'index.html' para GitHub Pages ---
    print("\n🌐 PASO 6: Preparando index.html para GitHub Pages...")
    try:
        latest_html = os.path.join(HISTORY_FOLDER, html_file)
        shutil.copy(latest_html, "index.html")
        print(f"✅ index.html actualizado con el resumen del día.")
        
        # También copiar el audio más reciente si existe
        if audio_file and os.path.exists(os.path.join(HISTORY_FOLDER, audio_file)):
            shutil.copy(os.path.join(HISTORY_FOLDER, audio_file), "resumen_ia.mp3")
            print(f"✅ resumen_ia.mp3 actualizado.")
        else:
            # Si no hay audio, eliminar el archivo de audio en la raíz si existe
            if os.path.exists("resumen_ia.mp3"):
                os.remove("resumen_ia.mp3")
                print("🗑️ Eliminado resumen_ia.mp3 antiguo (no hay audio nuevo)")
    except Exception as e:
        print(f"⚠️ Error al copiar archivos: {e}")

    # --- PASO 7: Limpiar histórico antiguo ---
    print(f"\n🗑️ PASO 7: Limpiando histórico (manteniendo {MAX_HISTORY_DAYS} días)...")
    cleanup_old_history()

    # --- PASO 8: Subir a Google Drive (opcional) ---
    if os.environ.get('PARENT_FOLDER_ID'):
        print("\n☁️ PASO 8: Subiendo archivos a Google Drive...")
        try:
            # Subir el HTML con fecha y el audio con fecha
            upload_daily_document(
                os.path.join(HISTORY_FOLDER, html_file), 
                os.path.join(HISTORY_FOLDER, audio_file) if audio_file else None
            )
            print("✅ Archivos subidos a Drive")
        except Exception as e:
            print(f"⚠️ Error al subir a Drive: {e}")
            print("   Los archivos se generaron localmente, pero no se subieron a Drive")
    else:
        print("\n⚠️ PARENT_FOLDER_ID no configurada. Omitiendo subida a Drive.")

    # --- PASO 9: Resumen final ---
    print("\n" + "="*60)
    print("✅ AGENTE COMPLETADO CON ÉXITO")
    print(f"📊 Resumen del día: {summary_data.get('summary', '')[:200]}...")
    print(f"📁 Archivos generados:")
    print(f"   - {HISTORY_FOLDER}/{html_file}")
    if audio_file:
        print(f"   - {HISTORY_FOLDER}/{audio_file}")
    print(f"   - index.html (copia más reciente para GitHub Pages)")
    if os.path.exists("resumen_ia.mp3"):
        print(f"   - resumen_ia.mp3 (copia más reciente)")
    print(f"📅 Historial: {MAX_HISTORY_DAYS} días disponibles.")
    print("="*60)
    
    return True

def run_agent_with_retry(max_retries=2):
    """Ejecuta el agente con reintentos en caso de errores transitorios."""
    import time
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n🔄 Reintento {attempt} de {max_retries}...")
            time.sleep(30)  # Esperar 30 segundos antes de reintentar
        
        if run_agent():
            return True
    
    print("\n❌ El agente falló después de todos los reintentos.")
    return False

# --- Punto de entrada principal ---
if __name__ == '__main__':
    import sys
    
    print("🚀 AGENTE DE INTELIGENCIA ARTIFICIAL - EBS")
    print(f"📅 Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    
    # Verificar que existe la carpeta de histórico al inicio
    ensure_history_folder()
    
    # Ejecutar el agente con reintentos
    success = run_agent_with_retry()
    
    # Código de salida para GitHub Actions
    sys.exit(0 if success else 1)