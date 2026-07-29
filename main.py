# main.py
import os
import sys
import json
from datetime import datetime

# Importar los módulos de nuestro agente
from youtube_fetcher import fetch_all_youtube_content, save_content_to_json
from summary_generator import generate_summary
from audio_generator import generate_audio
from document_generator import generate_html_document
from drive_uploader import upload_daily_document

# --- CONFIGURACIÓN DESDE VARIABLES DE ENTORNO ---
# Estas variables deben estar configuradas en GitHub Actions (como secretos)
# o en un archivo .env para pruebas locales
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
PARENT_FOLDER_ID = os.environ.get('PARENT_FOLDER_ID')

# Configuración adicional
MAX_TRANSCRIPT_LENGTH = 50000  # Caracteres máximos para la transcripción
AUDIO_FILENAME = "resumen_ia.mp3"
HTML_FILENAME = "index.html"
JSON_FILENAME = "youtube_content.json"

def verificar_configuracion():
    """Verifica que todas las variables de entorno necesarias estén configuradas."""
    print("\n=== Verificando configuración ===")
    errores = []
    
    if not YOUTUBE_API_KEY:
        errores.append("❌ YOUTUBE_API_KEY no está configurada")
    else:
        print("✅ YOUTUBE_API_KEY configurada")
    
    if not DEEPSEEK_API_KEY:
        errores.append("❌ DEEPSEEK_API_KEY no está configurada")
    else:
        print("✅ DEEPSEEK_API_KEY configurada")
    
    if not PARENT_FOLDER_ID:
        print("⚠️ PARENT_FOLDER_ID no configurada (opcional, para subir a Drive)")
    else:
        print("✅ PARENT_FOLDER_ID configurada")
    
    # Verificar que el archivo de cookies existe
    if os.path.exists('cookies.txt'):
        print("✅ Archivo cookies.txt encontrado")
    else:
        print("⚠️ Archivo cookies.txt no encontrado (la autenticación puede fallar)")
    
    if errores:
        print("\n❌ Errores encontrados:")
        for error in errores:
            print(f"  {error}")
        return False
    
    print("✅ Configuración verificada correctamente")
    return True

def run_agent():
    """Función principal que ejecuta todo el agente."""
    print("\n" + "="*50)
    print(f"🤖 INICIANDO AGENTE IA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 1. Verificar configuración
    if not verificar_configuracion():
        print("❌ Error de configuración. Deteniendo ejecución.")
        return False
    
    # 2. Obtener contenido de YouTube
    print("\n📹 PASO 1: Obteniendo contenido de YouTube...")
    try:
        videos = fetch_all_youtube_content()
        if not videos:
            print("❌ No se encontraron videos nuevos. Saliendo.")
            # Generar un documento de "sin novedades"
            generar_documento_sin_novedades()
            return False
        
        # Guardar el contenido en JSON para depuración
        save_content_to_json(videos, JSON_FILENAME)
        print(f"✅ Se encontraron {len(videos)} videos con transcripción")
    except Exception as e:
        print(f"❌ Error al obtener contenido de YouTube: {e}")
        return False
    
    # 3. Generar resumen con DeepSeek
    print("\n🧠 PASO 2: Generando resumen con DeepSeek...")
    try:
        summary_data = generate_summary(videos)
        if not summary_data or not summary_data.get('summary'):
            print("❌ No se pudo generar el resumen")
            return False
        print(f"✅ Resumen generado: {summary_data['summary'][:100]}...")
        print(f"   📰 {len(summary_data.get('news', []))} noticias extraídas")
    except Exception as e:
        print(f"❌ Error al generar resumen: {e}")
        return False
    
    # 4. Generar audio del resumen
    print("\n🎧 PASO 3: Generando audio...")
    try:
        summary_text = summary_data.get('summary', '')
        audio_file = generate_audio(summary_text, AUDIO_FILENAME)
        if audio_file:
            print(f"✅ Audio generado: {audio_file}")
        else:
            print("⚠️ No se pudo generar el audio, continuando sin él")
    except Exception as e:
        print(f"⚠️ Error al generar audio: {e}")
        print("   Continuando sin audio")
    
    # 5. Generar documento HTML
    print("\n📄 PASO 4: Generando documento HTML...")
    try:
        html_file = generate_html_document(
            summary_data, 
            audio_file if 'audio_file' in locals() and audio_file else "audio_no_disponible.mp3",
            HTML_FILENAME
        )
        print(f"✅ Documento HTML generado: {html_file}")
    except Exception as e:
        print(f"❌ Error al generar HTML: {e}")
        return False
    
    # 6. Subir a Google Drive
    if PARENT_FOLDER_ID:
        print("\n☁️ PASO 5: Subiendo archivos a Google Drive...")
        try:
            upload_daily_document(html_file, audio_file if 'audio_file' in locals() else None)
            print("✅ Archivos subidos a Drive")
        except Exception as e:
            print(f"⚠️ Error al subir a Drive: {e}")
            print("   Los archivos se generaron localmente, pero no se subieron a Drive")
    else:
        print("\n⚠️ PARENT_FOLDER_ID no configurada. Omitiendo subida a Drive.")
    
    # 7. Resumen final
    print("\n" + "="*50)
    print("✅ AGENTE COMPLETADO CON ÉXITO")
    print(f"📊 Resumen del día: {summary_data.get('summary', '')[:200]}...")
    print(f"📁 Archivos generados:")
    print(f"   - {HTML_FILENAME}")
    if 'audio_file' in locals() and audio_file:
        print(f"   - {AUDIO_FILENAME}")
    print(f"   - {JSON_FILENAME} (depuración)")
    print("="*50)
    
    return True

def generar_documento_sin_novedades():
    """Genera un documento HTML cuando no hay novedades."""
    print("\n📄 Generando documento 'sin novedades'...")
    
    summary_data = {
        "summary": "No se encontraron videos nuevos en los canales monitoreados en las últimas 24 horas.",
        "news": []
    }
    
    try:
        html_file = generate_html_document(summary_data, None, HTML_FILENAME)
        print(f"✅ Documento 'sin novedades' generado: {html_file}")
        
        # Intentar subir a Drive si está configurado
        if PARENT_FOLDER_ID:
            try:
                upload_daily_document(html_file, None)
                print("✅ Archivo subido a Drive")
            except Exception as e:
                print(f"⚠️ Error al subir a Drive: {e}")
    except Exception as e:
        print(f"❌ Error al generar documento 'sin novedades': {e}")

def run_agent_with_retry(max_retries=2):
    """Ejecuta el agente con reintentos en caso de errores transitorios."""
    for attempt in range(max_retries + 1):
        print(f"\n🔄 Intento {attempt + 1} de {max_retries + 1}")
        if run_agent():
            return True
        
        if attempt < max_retries:
            print(f"⏳ Esperando 30 segundos antes de reintentar...")
            time.sleep(30)
    
    print("\n❌ El agente falló después de todos los reintentos.")
    return False

# Punto de entrada principal
if __name__ == '__main__':
    import time  # Para el reintento
    
    print("🚀 AGENTE DE INTELIGENCIA ARTIFICIAL - EBS")
    print(f"📅 Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    
    # Ejecutar el agente con reintentos
    success = run_agent_with_retry()
    
    # Código de salida para GitHub Actions
    sys.exit(0 if success else 1)
