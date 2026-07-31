# summary_generator.py
import json
import requests
import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

# --- CONFIGURACIÓN ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_NEWS_TOTAL = 5  # REDUCIDO de 10 a 5
CACHE_FILE = "cache_summary.json"  # Archivo de caché para respuestas
# ---------------------

def load_cache():
    """Carga el caché de respuestas desde un archivo JSON."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    """Guarda el caché de respuestas en un archivo JSON."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Error al guardar caché: {e}")

def select_representative_news(news_items):
    """Selecciona noticias garantizando al menos una por canal de YouTube."""
    if not news_items:
        return []

    youtube_news = [item for item in news_items if item.get('tipo') == 'youtube']
    external_news = [item for item in news_items if item.get('tipo') == 'externo']

    channels = defaultdict(list)
    for item in youtube_news:
        fuente = item.get('fuente', 'Desconocido')
        if fuente.startswith('YouTube: '):
            canal = fuente.replace('YouTube: ', '')
        else:
            canal = fuente
        channels[canal].append(item)

    selected_news = []
    for canal, items in channels.items():
        if items:
            selected_news.append(items[0])
            print(f"📌 Seleccionada noticia de {canal}: {items[0].get('title', 'Sin título')}")

    remaining_slots = MAX_NEWS_TOTAL - len(selected_news)
    if remaining_slots > 0 and external_news:
        external_selected = external_news[:remaining_slots]
        selected_news.extend(external_selected)
        print(f"📌 Añadidas {len(external_selected)} noticias externas")

    if len(selected_news) > MAX_NEWS_TOTAL:
        selected_news = selected_news[:MAX_NEWS_TOTAL]

    print(f"✅ Total de noticias seleccionadas: {len(selected_news)}")
    return selected_news

def generate_summary(news_items):
    """
    Genera un resumen y una lista de noticias usando DeepSeek.
    Incluye caché de respuestas para evitar llamadas repetidas.
    """
    if not news_items:
        print("No hay datos de noticias para resumir.")
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada como variable de entorno.")
        return {"summary": "Error de configuración: clave API no encontrada.", "news": []}

    # --- PASO 1: Seleccionar noticias representativas ---
    print("\n🔍 Seleccionando noticias representativas...")
    selected_news = select_representative_news(news_items)
    
    if not selected_news:
        print("❌ No se seleccionaron noticias.")
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    # --- PASO 2: Construir el prompt (ESTANDARIZADO PARA CACHÉ) ---
    # Este prompt es largo y específico para que DeepSeek lo cachee
    system_prompt = """
    Eres un asistente de IA especializado en analizar y resumir noticias sobre tecnología e inteligencia artificial.

    **INSTRUCCIÓN OBLIGATORIA:** Todo el texto que generes (títulos, resúmenes, fuentes y el resumen general) DEBE estar en español. Si la noticia original está en inglés, debes traducirla al español.

    Tu tarea es procesar la información de las siguientes noticias (que pueden venir de videos de YouTube o de fuentes escritas) y generar:

    1. Un **resumen general** en español de 2-3 párrafos que capture las ideas, anuncios y tendencias más importantes del día en el mundo de la IA.
    2. Una lista de **noticias individuales** en formato JSON.

    Para la lista de noticias, cada elemento debe ser un objeto con:
    - 'title': El título de la noticia (TRADUCIDO al español).
    - 'resumen': Un resumen breve (máximo 2 frases) de la noticia (TRADUCIDO al español).
    - 'fuente': El nombre de la fuente (ej. "YouTube: EDteam", "TechCrunch").
    - 'tipo': Indica si la noticia viene de 'youtube' o de 'externo'.
    - 'url': El enlace original a la noticia o video de YouTube.

    **IMPORTANTE:** NO devuelvas textos en inglés. Todo el contenido debe estar en español.
    Sé conciso, relevante y enfócate en los hechos y novedades clave para la industria de la IA.
    """
    
    # Construir el texto de noticias (recortado)
    news_info_text = ""
    for i, item in enumerate(selected_news):
        titulo = item.get('title', 'Sin título')
        fuente = item.get('fuente', 'Fuente desconocida')
        resumen = item.get('resumen', '')
        tipo = item.get('tipo', 'desconocido')
        url = item.get('url', '#')
        
        if tipo == 'youtube':
            contexto = resumen[:200] if resumen else 'Transcripción no disponible'
            etiqueta = "🎥 [YouTube]"
        else:
            contexto = resumen[:200] if resumen else 'Resumen no disponible'
            etiqueta = "📰 [Fuente externa]"
        
        news_info_text += f"Noticia {i+1}: {etiqueta}\n"
        news_info_text += f"Título: {titulo}\n"
        news_info_text += f"Fuente: {fuente}\n"
        news_info_text += f"URL: {url}\n"
        news_info_text += f"Resumen: {contexto}\n\n"

    user_prompt = f"Aquí está la lista de noticias seleccionadas del día (algunas pueden estar en inglés, pero tú debes traducirlas al español):\n\n{news_info_text}"

    # --- PASO 3: Verificar caché ---
    cache = load_cache()
    cache_key = hashlib.md5((system_prompt + user_prompt).encode()).hexdigest()
    
    if cache_key in cache:
        print("📦 Respuesta obtenida del caché (ahorrando tokens).")
        return cache[cache_key]

    # --- PASO 4: Llamar a la API de DeepSeek ---
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\nGenera tu respuesta en formato JSON con las claves 'summary' (string) y 'news' (lista de objetos con 'title' (en español), 'resumen' (en español), 'fuente', 'tipo' y 'url')."}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        try:
            summary_data = json.loads(ai_response_content)
            if 'summary' not in summary_data:
                summary_data['summary'] = "Resumen no disponible."
            if 'news' not in summary_data:
                summary_data['news'] = []
            
            # Guardar en caché
            cache[cache_key] = summary_data
            save_cache(cache)
            return summary_data
        except json.JSONDecodeError:
            print(f"❌ Error: El modelo no devolvió un JSON válido. Respuesta: {ai_response_content[:200]}...")
            return {
                "summary": "Se generó un resumen, pero hubo un error al procesar el formato.",
                "news": []
            }
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al llamar a la API de DeepSeek: {e}")
        return {
            "summary": "Error de conexión con DeepSeek. No se pudo generar el resumen.",
            "news": []
        }
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return {
            "summary": "Error inesperado al generar el resumen.",
            "news": []
        }

# --- Función para pruebas ---
if __name__ == '__main__':
    print("=== Probando summary_generator.py ===\n")
    
    if not DEEPSEEK_API_KEY:
        print("⚠️ DEEPSEEK_API_KEY no configurada. Usando datos de ejemplo para prueba.")
    
    test_news = [
        {
            "title": "OpenAI anuncia GPT-5 con capacidad de 1M de tokens",
            "resumen": "OpenAI ha presentado oficialmente GPT-5, su nuevo modelo con capacidad de contexto de 1 millón de tokens.",
            "fuente": "YouTube: EDteam",
            "url": "https://www.youtube.com/watch?v=123",
            "tipo": "youtube"
        },
        {
            "title": "Kimi K3 ya está aquí: el modelo chino que desafía a GPT",
            "resumen": "Kimi K3 es el modelo abierto de crecimiento más rápido en la historia.",
            "fuente": "YouTube: XavierMitjana",
            "url": "https://www.youtube.com/watch?v=456",
            "tipo": "youtube"
        },
        {
            "title": "Microsoft is openly competing with OpenAI, Anthropic more than ever",
            "resumen": "Microsoft pitched its own homegrown AI models.",
            "fuente": "TechCrunch",
            "url": "https://techcrunch.com/...",
            "tipo": "externo"
        },
        {
            "title": "Google lanza Gemini Ultra para empresas",
            "resumen": "Google ha anunciado Gemini Ultra, su modelo más avanzado.",
            "fuente": "VentureBeat",
            "url": "https://venturebeat.com/...",
            "tipo": "externo"
        }
    ]
    
    summary = generate_summary(test_news)
    print("\n📊 Resumen generado:")
    print(json.dumps(summary, indent=4, ensure_ascii=False))