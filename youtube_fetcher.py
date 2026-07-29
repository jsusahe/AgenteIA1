# youtube_fetcher.py
import os
import json
from datetime import datetime, timedelta
from yt_dlp import YoutubeDL
import requests
import time

# --- CONFIGURACIÓN (MODIFICA AQUÍ TUS DATOS) ---
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')  # Leer desde variable de entorno
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')  # Leer desde variable de entorno
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Lista de canales de YouTube a monitorear
CHANNEL_URLS = [
    "https://www.youtube.com/@XavierMitjana",
    "https://www.youtube.com/@EDteam",
    "https://www.youtube.com/@marc_vidal"
]
# Puedes añadir más canales a esta lista en el futuro.
# ---------------------------------------------

def get_channel_id(url):
    """Obtiene el ID del canal a partir de su URL usando la API de YouTube."""
    # Extrae el nombre de usuario del @ de la URL
    username = url.split('@')[-1]
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': username,
        'type': 'channel',
        'maxResults': 1,
        'key': YOUTUBE_API_KEY
    }
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data['items']:
            return data['items'][0]['snippet']['channelId']
        else:
            print(f"No se encontró el canal para el usuario: {username}")
            return None
    except Exception as e:
        print(f"Error al obtener el ID del canal para {username}: {e}")
        return None

def get_videos_from_channel(channel_id):
    """Obtiene los videos de un canal específico de los últimos 2 días."""
    # YouTube usa la zona horaria UTC. Restamos 2 días para asegurar capturar todo.
    published_after = (datetime.utcnow() - timedelta(days=2)).isoformat("T") + "Z"
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'channelId': channel_id,
        'order': 'date',
        'type': 'video',
        'publishedAfter': published_after,
        'maxResults': 20,  # Puedes ajustar este número
        'key': YOUTUBE_API_KEY
    }
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        videos = []
        for item in data.get('items', []):
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            # Filtro opcional para evitar shorts o videos no deseados
            # if '#shorts' in title.lower():
            #    continue
            videos.append({
                'id': video_id,
                'title': title,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'description': item['snippet']['description'],
                'published_at': item['snippet']['publishedAt']
            })
        return videos
    except Exception as e:
        print(f"Error al obtener videos del canal {channel_id}: {e}")
        return []

def get_transcript(video_id):
    """Obtiene la transcripción de un video usando yt-dlp."""
    # Configuración optimizada para evitar errores de formato y resolver desafíos JS
    ydl_opts = {
        'quiet': True,                     # No mostrar salida innecesaria
        'skip_download': True,             # No descargar el video
        'writesubtitles': True,            # Intentar descargar subtítulos
        'writeautomaticsub': True,         # Si no hay, usar los automáticos
        'subtitleslangs': ['es', 'en'],    # Priorizar español e inglés
        'extract_flat': True,              # Extraer información de manera simplificada
        'cookiefile': 'cookies.txt',       # Usar el archivo de cookies para autenticación
        'ignoreerrors': True,              # Ignorar errores de formato y continuar
        'no_warnings': True,               # Suprimir advertencias
        'verbose': False,                  # No mostrar logs detallados (cambiar a True para depurar)
        # NUEVA OPCIÓN: Habilita la descarga de componentes remotos para resolver desafíos JS
        'remote_components': ['ejs:github'],  # Descarga los scripts necesarios desde GitHub
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Obtener información del video
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            # Si no hay información, salir
            if not info:
                print(f"No se pudo obtener información del video {video_id}")
                return None
                
            # Buscar la transcripción en los subtítulos
            subs = info.get('requested_subtitles', info.get('subtitles', {}))
            if subs:
                # Buscar el idioma (español o inglés)
                for lang in ['es', 'en']:
                    if lang in subs:
                        sub_url = subs[lang]['url']
                        try:
                            sub_response = requests.get(sub_url, timeout=15)
                            if sub_response.status_code == 200:
                                # Procesar la transcripción (limpiar formato)
                                transcript_lines = []
                                for line in sub_response.text.split('\n'):
                                    # Ignorar líneas de timestamps y marcadores
                                    if '-->' not in line and not line.startswith('WEBVTT') and line.strip() != '':
                                        # Limpiar etiquetas HTML básicas
                                        clean_line = line.replace('<c>', '').replace('</c>', '').replace('\\n', ' ')
                                        transcript_lines.append(clean_line)
                                transcript = " ".join(transcript_lines)
                                if transcript.strip():
                                    return transcript
                                else:
                                    print(f"Transcripción vacía para {video_id}")
                                    return None
                        except requests.exceptions.RequestException as e:
                            print(f"Error al descargar subtítulos de {video_id}: {e}")
                            continue
                print(f"No se encontraron subtítulos en español o inglés para {video_id}")
            else:
                print(f"No hay subtítulos disponibles para el video {video_id}")
            return None
    except Exception as e:
        print(f"Error al obtener la transcripción de {video_id}: {e}")
        return None

def fetch_all_youtube_content():
    """Función principal para buscar contenido de todos los canales."""
    print("--- Iniciando búsqueda en YouTube ---")
    all_videos_with_transcripts = []
    
    # Verificar que el archivo de cookies existe
    if not os.path.exists('cookies.txt'):
        print("⚠️ ADVERTENCIA: No se encontró el archivo cookies.txt. La autenticación puede fallar.")
    else:
        print("✅ Archivo cookies.txt encontrado.")
    
    for channel_url in CHANNEL_URLS:
        print(f"\n🔍 Procesando canal: {channel_url}")
        channel_id = get_channel_id(channel_url)
        if not channel_id:
            print(f"❌ No se pudo obtener el ID del canal para {channel_url}")
            continue
        
        videos = get_videos_from_channel(channel_id)
        print(f"📹 Se encontraron {len(videos)} videos en {channel_url}")
        
        for video in videos:
            print(f"  ⏳ Procesando: {video['title']} ({video['id']})")
            transcript = get_transcript(video['id'])
            if transcript:
                # Limitar la longitud de la transcripción para no exceder el contexto de DeepSeek
                MAX_LENGTH = 50000  # Caracteres
                if len(transcript) > MAX_LENGTH:
                    transcript = transcript[:MAX_LENGTH] + "... (transcripción truncada)"
                video['transcript'] = transcript
                all_videos_with_transcripts.append(video)
                print(f"  ✅ Transcripción obtenida ({len(transcript)} caracteres)")
            else:
                print(f"  ❌ No se pudo obtener transcripción")
            
            # Pequeña pausa para no sobrecargar la API de YouTube
            time.sleep(0.5)
    
    print(f"\n--- Búsqueda completada. {len(all_videos_with_transcripts)} videos con transcripción encontrados. ---")
    return all_videos_with_transcripts

def save_content_to_json(content, filename="youtube_content.json"):
    """Guarda el contenido en un archivo JSON para depuración."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=4, ensure_ascii=False)
        print(f"✅ Contenido guardado en {filename}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar {filename}: {e}")
        return False

# Función principal para ejecutar el módulo de forma independiente
if __name__ == '__main__':
    print("=== YouTube Fetcher - Modo de Prueba ===")
    
    # Verificar que las variables de entorno estén configuradas
    if not YOUTUBE_API_KEY:
        print("❌ ERROR: YOUTUBE_API_KEY no está configurada como variable de entorno.")
        print("   Asegúrate de establecerla con: export YOUTUBE_API_KEY='tu_clave' (Linux/Mac)")
        print("   o set YOUTUBE_API_KEY=tu_clave (Windows CMD)")
        exit(1)
    
    # Ejecutar la búsqueda
    content = fetch_all_youtube_content()
    
    if content:
        # Guardar el contenido en un archivo JSON para inspección
        save_content_to_json(content)
        
        # Mostrar un resumen
        print("\n📊 Resumen de contenido encontrado:")
        for i, video in enumerate(content, 1):
            transcript_preview = video.get('transcript', '')[:100] + "..."
            print(f"{i}. {video['title']}")
            print(f"   Transcripción: {transcript_preview}")
            print(f"   URL: {video['url']}\n")
    else:
        print("❌ No se encontró ningún contenido nuevo.")
        print("   Posibles causas:")
        print("   - Los canales no han subido videos en los últimos 2 días.")
        print("   - Las cookies de YouTube han expirado (actualiza cookies.txt).")
        print("   - La API key de YouTube no tiene permisos suficientes.")
        print("   - Los videos no tienen subtítulos disponibles.")