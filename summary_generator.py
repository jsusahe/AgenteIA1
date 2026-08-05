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

def clean_and_extract_json(text):
    json_pattern = r'(\{[\s\S]*"summary"[\s\S]*"news"[\s\S]*\}|\[[\s\S]*\])'
    match = re.search(json_pattern, text)
    
    if match:
        json_str = match.group(1)
        json_str = ''.join(ch for ch in json_str if ord(ch) >= 32 or ch in '\n\r\t')
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error al parsear JSON: {e}")
            try:
                fixed = re.sub(r"(?<!\\)'", '"', json_str)
                return json.loads(fixed)
            except:
                pass
            
            try:
                summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', json_str)
                news_matches = re.findall(r'"title"\s*:\s*"([^"]*)"', json_str)
                
                if summary_match and news_matches:
                    return {
                        "summary": summary_match.group(1),
                        "news": [{"title": t, "resumen": "Noticia destacada", "fuente": "Fuente externa", "tipo": "externo", "url": "#"} for t in news_matches[:5]]
                    }
            except:
                pass
    
    print("⚠️ No se pudo extraer JSON. Construyendo resumen básico...")
    lines = text.split('\n')
    summary_lines = [line for line in lines if len(line) > 50 and not line.startswith('{')]
    summary_text = " ".join(summary_lines[:5]) if summary_lines else "Resumen no disponible."
    
    return {
        "summary": summary_text[:500],
        "news": []
    }

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

    # --- Prompt mejorado para forzar resumen de TODAS las noticias ---
    system_prompt = """
    Eres un asistente que resume noticias de IA. Genera un JSON válido con:
    {
      "summary": "Resumen general en español (3-4 párrafos) que cubra TODAS las noticias listadas. Menciona cada una de las noticias al menos una vez.",
      "news": [
        {
          "title": "Título de la noticia",
          "resumen": "Resumen extenso (mínimo 3 renglones)",
          "fuente": "Nombre de la fuente",
          "tipo": "youtube o externo",
          "url": "URL de la noticia"
        }
      ]
    }
    **INSTRUCCIÓN OBLIGATORIA:** El resumen general DEBE mencionar explícitamente cada una de las noticias presentadas. No omitas ninguna.
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
        contexto = resumen[:300] if resumen else 'Sin resumen'
        
        news_info_text += f"{i+1}. {etiqueta}\n"
        news_info_text += f"Título: {titulo}\n"
        news_info_text += f"Fuente: {fuente}\n"
        news_info_text += f"URL: {url}\n"
        news_info_text += f"Resumen: {contexto}\n\n"

    user_prompt = f"Noticias del día:\n\n{news_info_text}\n\nGenera el JSON con el resumen general (que cubra TODAS las noticias) y las noticias destacadas."

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
            {"role": "user", "content": user_prompt + "\n\nDevuelve SOLO el JSON, sin texto adicional. El resumen general DEBE mencionar TODAS las noticias."}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
        "max_tokens": 2500
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        print(f"📝 Respuesta de DeepSeek (primeros 200 caracteres): {ai_response_content[:200]}...")
        
        summary_data = clean_and_extract_json(ai_response_content)
        
        if 'summary' not in summary_data:
            summary_data['summary'] = "Resumen no disponible."
        if 'news' not in summary_data:
            summary_data['news'] = []
        
        # Verificar que el resumen mencione todas las noticias
        total_news = len(selected_news)
        summary_text = summary_data.get('summary', '')
        news_titles = [item.get('title', '') for item in selected_news]
        
        # Si el resumen no menciona al menos la mitad de las noticias, forzar un resumen más completo
        mentioned = sum(1 for title in news_titles if title.lower() in summary_text.lower())
        if mentioned < total_news // 2:
            print(f"⚠️ El resumen solo menciona {mentioned} de {total_news} noticias. Forzando resumen más completo...")
            # Añadir un párrafo adicional con las noticias faltantes
            missing_titles = [t for t in news_titles if t.lower() not in summary_text.lower()]
            if missing_titles:
                extra_paragraph = "\n\nAdemás, otras noticias relevantes incluyen: " + ", ".join(missing_titles[:5])
                summary_data['summary'] = summary_data['summary'] + extra_paragraph
        
        # Verificar longitud de resúmenes
        for item in summary_data.get('news', []):
            if len(item.get('resumen', '')) < 150:
                if item.get('resumen', ''):
                    item['resumen'] = item['resumen'] + " Este tema es relevante para el sector tecnológico y la innovación en inteligencia artificial."
        
        cache[cache_key] = summary_data
        save_cache(cache)
        return summary_data
        
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
        },
        {
            "title": "Google lanza Gemini Ultra para empresas",
            "resumen": "Google ha anunciado Gemini Ultra, su modelo más avanzado.",
            "fuente": "VentureBeat",
            "url": "https://venturebeat.com/...",
            "tipo": "externo"
        },
        {
            "title": "Anthropic publica su posición sobre modelos abiertos",
            "resumen": "Anthropic ha publicado un documento oficial sobre su postura.",
            "fuente": "Wired",
            "url": "https://wired.com/...",
            "tipo": "externo"
        }
    ]
    
    summary = generate_summary(test_news)
    print("\n📊 Resumen generado:")
    print(json.dumps(summary, indent=4, ensure_ascii=False))