# youtube_fetcher.py
from dotenv import load_dotenv
load_dotenv()
import os
import json
from datetime import datetime, timedelta
from yt_dlp import YoutubeDL
import requests
import time

# --- CONFIGURACIÓN ---
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

def load_youtube_channels():
    config_file = "config_youtube.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [item['url'] for item in data.get('channels', [])]
        except Exception as e:
            print(f"⚠️ Error al cargar {config_file}: {e}")
            return []
    else:
        print(f"⚠️ Archivo {config_file} no encontrado. Usando lista por defecto.")
        return [
            "https://www.youtube.com/@XavierMitjana",
            "https://www.youtube.com/@EDteam",
            "https://www.youtube.com/@marc_vidal"
        ]

CHANNEL_URLS = load_youtube_channels()
# ---------------------------------------------

def get_channel_id(url):
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
    published_after = (datetime.utcnow() - timedelta(days=2)).isoformat("T") + "Z"
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'channelId': channel_id,
        'order': 'date',
        'type': 'video',
        'publishedAfter': published_after,
        'maxResults': 20,
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
            channel_name = item['snippet']['channelTitle']
            videos.append({
                'id': video_id,
                'title': title,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'description': item['snippet']['description'],
                'published_at': item['snippet']['publishedAt'],
                'channel': channel_name
            })
        return videos
    except Exception as e:
        print(f"Error al obtener videos del canal {channel_id}: {e}")
        return []

def get_transcript(video_id):
    """
    Obtiene la transcripción de un video usando yt-dlp con cliente web.
    """
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['es', 'en'],
        'cookiefile': 'cookies.txt',
        'ignoreerrors': True,
        'no_warnings': True,
        'verbose': False,
        'format': 'bestaudio/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['web'],  # Usar cliente web
                'skip': ['hls', 'dash'],
            }
        },
        'retries': 5,
        'fragment_retries': 5,
        'timeout': 90,
        'extract_flat': 'in_playlist',  # Extraer solo datos básicos
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if not info:
                print(f"No se pudo obtener información del video {video_id}")
                return get_transcript_fallback(video_id)
                
            subs = info.get('requested_subtitles', info.get('subtitles', {}))
            if subs:
                for lang in ['es', 'en']:
                    if lang in subs:
                        sub_url = subs[lang]['url']
                        try:
                            sub_response = requests.get(sub_url, timeout=30)
                            if sub_response.status_code == 200:
                                transcript_lines = []
                                for line in sub_response.text.split('\n'):
                                    if '-->' not in line and not line.startswith('WEBVTT') and line.strip() != '':
                                        clean_line = line.replace('<c>', '').replace('</c>', '').replace('\\n', ' ')
                                        transcript_lines.append(clean_line)
                                transcript = " ".join(transcript_lines)
                                if transcript.strip():
                                    return transcript
                        except requests.exceptions.RequestException as e:
                            print(f"Error al descargar subtítulos de {video_id}: {e}")
                            continue
                print(f"No se encontraron subtítulos en español o inglés para {video_id}")
            else:
                print(f"No hay subtítulos disponibles para el video {video_id}")
            return None
    except Exception as e:
        print(f"Error al obtener la transcripción de {video_id}: {e}")
        return get_transcript_fallback(video_id)

def get_transcript_fallback(video_id):
    """
    Estrategia de respaldo sin extract_flat.
    """
    print(f"🔄 Usando estrategia de respaldo para {video_id}...")
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['es', 'en'],
        'cookiefile': 'cookies.txt',
        'ignoreerrors': True,
        'no_warnings': True,
        'verbose': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['web'],
                'skip': ['hls', 'dash'],
            }
        },
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if not info:
                print(f"No se pudo obtener información del video {video_id} en el respaldo")
                return None
            subs = info.get('requested_subtitles', info.get('subtitles', {}))
            if subs:
                for lang in ['es', 'en']:
                    if lang in subs:
                        sub_url = subs[lang]['url']
                        try:
                            sub_response = requests.get(sub_url, timeout=30)
                            if sub_response.status_code == 200:
                                transcript_lines = []
                                for line in sub_response.text.split('\n'):
                                    if '-->' not in line and not line.startswith('WEBVTT') and line.strip() != '':
                                        clean_line = line.replace('<c>', '').replace('</c>', '').replace('\\n', ' ')
                                        transcript_lines.append(clean_line)
                                transcript = " ".join(transcript_lines)
                                if transcript.strip():
                                    return transcript
                        except:
                            continue
            return None
    except Exception as e:
        print(f"Error en respaldo para {video_id}: {e}")
        return None

def fetch_all_youtube_content():
    print("--- Iniciando búsqueda en YouTube ---")
    all_videos_with_transcripts = []
    
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
                MAX_LENGTH = 50000
                if len(transcript) > MAX_LENGTH:
                    transcript = transcript[:MAX_LENGTH] + "... (transcripción truncada)"
                video['transcript'] = transcript
                all_videos_with_transcripts.append(video)
                print(f"  ✅ Transcripción obtenida ({len(transcript)} caracteres)")
            else:
                print(f"  ❌ No se pudo obtener transcripción")
            
            time.sleep(2)
    
    print(f"\n--- Búsqueda completada. {len(all_videos_with_transcripts)} videos con transcripción encontrados. ---")
    return all_videos_with_transcripts

def save_content_to_json(content, filename="youtube_content.json"):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=4, ensure_ascii=False)
        print(f"✅ Contenido guardado en {filename}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar {filename}: {e}")
        return False

if __name__ == '__main__':
    print("=== YouTube Fetcher - Modo de Prueba ===")
    
    if not YOUTUBE_API_KEY:
        print("❌ ERROR: YOUTUBE_API_KEY no está configurada como variable de entorno.")
        exit(1)
    
    content = fetch_all_youtube_content()
    
    if content:
        save_content_to_json(content)
        print("\n📊 Resumen de contenido encontrado:")
        for i, video in enumerate(content, 1):
            transcript_preview = video.get('transcript', '')[:100] + "..."
            print(f"{i}. {video['title']}")
            print(f"   Canal: {video.get('channel', 'Desconocido')}")
            print(f"   Transcripción: {transcript_preview}")
            print(f"   URL: {video['url']}\n")
    else:
        print("❌ No se encontró ningún contenido nuevo.")