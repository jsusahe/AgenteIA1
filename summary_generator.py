# summary_generator.py
import json
import requests
import os
import hashlib
import re
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

# --- CONFIGURACIÓN ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_NEWS_TOTAL = 10
MIN_NEWS_TOTAL = 7
CACHE_FILE = "cache_summary.json"
# ---------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Error al guardar caché: {e}")

def select_representative_news(news_items):
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

    # FORZAR al menos MIN_NEWS_TOTAL noticias
    while len(selected_news) < MIN_NEWS_TOTAL:
        if external_news:
            for article in external_news:
                if article not in selected_news:
                    selected_news.append(article)
                    print(f"📌 Añadida noticia externa forzada: {article.get('title', 'Sin título')[:50]}...")
                    break
            else:
                break
        else:
            break

    if len(selected_news) < MIN_NEWS_TOTAL and selected_news:
        while len(selected_news) < MIN_NEWS_TOTAL:
            selected_news.append(selected_news[0])
            print(f"📌 Duplicada noticia para alcanzar mínimo: {selected_news[0].get('title', 'Sin título')[:50]}...")

    if len(selected_news) > MAX_NEWS_TOTAL:
        selected_news = selected_news[:MAX_NEWS_TOTAL]

    print(f"✅ Total de noticias seleccionadas: {len(selected_news)} (mínimo: {MIN_NEWS_TOTAL})")
    return selected_news

def clean_json_response(response_text):
    """
    Limpia la respuesta de DeepSeek para extraer el JSON.
    Maneja texto adicional antes o después del JSON.
    """
    # Buscar patrones de JSON (inicio con { o [ )
    json_match = re.search(r'(\{.*\}|\[.*\])', response_text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    return response_text

def generate_summary(news_items):
    if not news_items:
        print("No hay datos de noticias para resumir.")
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada.")
        return {"summary": "Error de configuración: clave API no encontrada.", "news": []}

    print("\n🔍 Seleccionando noticias representativas...")
    selected_news = select_representative_news(news_items)
    
    if not selected_news:
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    # --- Construir el prompt (más compacto para evitar truncamiento) ---
    system_prompt = """
    Eres un asistente que resume noticias de IA. Genera un JSON con:
    - 'summary': Resumen general en español (3-4 párrafos).
    - 'news': Lista de objetos con 'title', 'resumen' (mínimo 3 renglones), 'fuente', 'tipo' (youtube/externo), 'url'.
    Todo en español. No añadas texto fuera del JSON.
    """

    news_info_text = ""
    for i, item in enumerate(selected_news):
        titulo = item.get('title', 'Sin título')
        fuente = item.get('fuente', 'Fuente desconocida')
        resumen = item.get('resumen', '')
        tipo = item.get('tipo', 'desconocido')
        url = item.get('url', '#')
        
        etiqueta = "🎥 [YouTube]" if tipo == 'youtube' else "📰 [Fuente externa]"
        contexto = resumen[:200] if resumen else 'Sin resumen'
        
        news_info_text += f"{i+1}. {etiqueta} Título: {titulo}\n"
        news_info_text += f"   Fuente: {fuente}\n"
        news_info_text += f"   URL: {url}\n"
        news_info_text += f"   Resumen: {contexto}\n\n"

    user_prompt = f"Noticias del día:\n\n{news_info_text}\n\nGenera el JSON con el resumen general y las noticias destacadas."

    # --- Verificar caché ---
    cache = load_cache()
    cache_key = hashlib.md5((system_prompt + user_prompt).encode()).hexdigest()
    
    if cache_key in cache:
        print("📦 Respuesta obtenida del caché.")
        return cache[cache_key]

    # --- Llamar a la API ---
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\nDevuelve SOLO el JSON, sin texto adicional."}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "max_tokens": 2000
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        # Limpiar la respuesta para extraer solo el JSON
        cleaned_response = clean_json_response(ai_response_content)
        
        try:
            summary_data = json.loads(cleaned_response)
            if 'summary' not in summary_data:
                summary_data['summary'] = "Resumen no disponible."
            if 'news' not in summary_data:
                summary_data['news'] = []
            
            # Verificar longitud de resúmenes
            for item in summary_data.get('news', []):
                if len(item.get('resumen', '')) < 150:
                    if item.get('resumen', ''):
                        item['resumen'] = item['resumen'] + " Este tema es relevante para el sector tecnológico y la innovación en inteligencia artificial."
            
            cache[cache_key] = summary_data
            save_cache(cache)
            return summary_data
            
        except json.JSONDecodeError:
            print(f"❌ Error al parsear JSON. Respuesta original: {ai_response_content[:500]}...")
            # Intento de extraer JSON con expresiones regulares más flexibles
            try:
                # Buscar cualquier estructura JSON
                json_match = re.search(r'\{[^{]*"summary"[^}]*"news"[^}]*\}', ai_response_content, re.DOTALL)
                if json_match:
                    summary_data = json.loads(json_match.group())
                    if 'summary' in summary_data and 'news' in summary_data:
                        print("✅ JSON extraído con expresión regular.")
                        return summary_data
            except:
                pass
            
            return {
                "summary": "Se generó un resumen, pero hubo un error al procesar el formato.",
                "news": []
            }
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al llamar a la API de DeepSeek: {e}")
        return {
            "summary": "Error de conexión con DeepSeek.",
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
        print("⚠️ DEEPSEEK_API_KEY no configurada.")
    
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
            "title": "Microsoft compite abiertamente con OpenAI y Anthropic",
            "resumen": "Microsoft ha lanzado sus propios modelos de IA.",
            "fuente": "TechCrunch",
            "url": "https://techcrunch.com/...",
            "tipo": "externo"
        }
    ]
    
    summary = generate_summary(test_news)
    print("\n📊 Resumen generado:")
    print(json.dumps(summary, indent=4, ensure_ascii=False))