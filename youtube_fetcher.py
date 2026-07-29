# youtube_fetcher.py
import os
import json
from datetime import datetime, timedelta
from yt_dlp import YoutubeDL
import requests
import time

# --- CONFIGURACIÓN (MODIFICA AQUÍ TUS DATOS) ---
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY') # <--- Pega tu clave aquí
CHANNEL_URLS = [
    "https://www.youtube.com/@XavierMitjana",
    "https://www.youtube.com/@EDteam",
    "https://www.youtube.com/@marc_vidal"
]
# Puedes añadir más canales a esta lista en el futuro.

# DeepSeek API details
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') # <--- Pega tu clave aquí
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions" # URL para el modelo de chat
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
        'maxResults': 20, # Puede que quieras ajustar esto
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
            # Filtra para evitar obtener shorts o videos no deseados si es necesario
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
    BROWSER = 'chrome'
    # Los parámetros de yt-dlp para obtener solo la transcripción
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['es', 'en'], # Intenta español primero, luego inglés
        'extract_flat': 'in_playlist',
        'cookiesfrombrowser': (BROWSER,),
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # yt-dlp puede obtener la información de la transcripción directamente
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            # La transcripción suele estar en 'requested_subtitles' o 'subtitles'
            subs = info.get('requested_subtitles', info.get('subtitles', {}))
            if subs:
                # Busca el idioma que pediste (español o inglés)
                for lang in ['es', 'en']:
                    if lang in subs:
                        # Descarga la transcripción en el idioma encontrado
                        sub_url = subs[lang]['url']
                        sub_response = requests.get(sub_url)
                        if sub_response.status_code == 200:
                            # yt-dlp devuelve la transcripción en formato WebVTT o similar
                            # Procesamiento simple para extraer solo el texto
                            transcript_lines = []
                            for line in sub_response.text.split('\n'):
                                # Intenta extraer líneas de texto, ignorando timestamps y marcadores
                                if '-->' not in line and not line.startswith('WEBVTT') and line.strip() != '':
                                    # Limpiar etiquetas HTML básicas si las hay
                                    clean_line = line.replace('<c>', '').replace('</c>', '').replace('\\n', ' ')
                                    transcript_lines.append(clean_line)
                            return " ".join(transcript_lines)
                print(f"No se encontró transcripción en español o inglés para {video_id}")
            else:
                print(f"No hay transcripciones disponibles para el video {video_id}")
            return None
    except Exception as e:
        print(f"Error al obtener la transcripción de {video_id}: {e}")
        return None

def fetch_all_youtube_content():
    """Función principal para buscar contenido de todos los canales."""
    print("--- Iniciando búsqueda en YouTube ---")
    all_videos_with_transcripts = []
    for channel_url in CHANNEL_URLS:
        channel_id = get_channel_id(channel_url)
        if not channel_id:
            continue
        videos = get_videos_from_channel(channel_id)
        print(f"Se encontraron {len(videos)} videos en {channel_url}")
        for video in videos:
            print(f"  Procesando: {video['title']} ({video['id']})")
            transcript = get_transcript(video['id'])
            if transcript:
                # Limitar la longitud de la transcripción para no exceder el contexto de DeepSeek
                # (aproximadamente 1M de tokens para DeepSeek-V4, pero es bueno ser precavido) [citation:2]
                MAX_LENGTH = 50000 # Caracteres
                if len(transcript) > MAX_LENGTH:
                    transcript = transcript[:MAX_LENGTH] + "... (transcripción truncada)"
                video['transcript'] = transcript
                all_videos_with_transcripts.append(video)
            time.sleep(0.5) # Pequeña pausa para no sobrecargar la API de YouTube
    print(f"--- Búsqueda completada. {len(all_videos_with_transcripts)} videos con transcripción encontrados. ---")
    return all_videos_with_transcripts

# La función main se usará para probar este módulo
if __name__ == '__main__':
    content = fetch_all_youtube_content()
    if content:
        # Guarda un JSON de ejemplo para inspección
        with open('youtube_content.json', 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=4, ensure_ascii=False)
        print("Contenido guardado en youtube_content.json")
    else:
        print("No se encontró ningún contenido nuevo.")
