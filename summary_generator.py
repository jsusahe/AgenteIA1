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

def extract_json_from_response(text):
    """
    Intenta extraer un JSON válido de la respuesta de DeepSeek usando múltiples estrategias.
    """
    # ESTRATEGIA 1: Buscar JSON con formato estándar
    json_pattern = r'(\{[\s\S]*"summary"[\s\S]*"news"[\s\S]*\})'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass

    # ESTRATEGIA 2: Buscar cualquier estructura JSON que contenga 'summary' y 'news'
    json_pattern2 = r'(\{[^{}]*"summary"[^{}]*"news"[^{}]*\})'
    match = re.search(json_pattern2, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass

    # ESTRATEGIA 3: Buscar un objeto JSON completo (más flexible)
    start = text.find('{')
    if start != -1:
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            json_str = text[start:end+1]
            try:
                return json.loads(json_str)
            except:
                json_str = re.sub(r'(?<!\\)\'', '"', json_str)
                json_str = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass

    print("⚠️ No se pudo extraer JSON de la respuesta.")
    return None

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

    # --- Prompt mejorado para forzar JSON con lista de noticias ---
    system_prompt = """
    Eres un asistente que resume noticias de IA. **DEBES** generar un JSON válido con la siguiente estructura EXACTA:

    {
      "summary": "Resumen general en español (3-4 párrafos) que mencione TODAS las noticias listadas.",
      "news": [
        {
          "title": "Título de la noticia 1",
          "resumen": "Resumen extenso de la noticia 1 (mínimo 3 renglones)",
          "fuente": "Nombre de la fuente",
          "tipo": "youtube o externo",
          "url": "URL de la noticia"
        },
        {
          "title": "Título de la noticia 2",
          "resumen": "Resumen extenso de la noticia 2 (mínimo 3 renglones)",
          "fuente": "Nombre de la fuente",
          "tipo": "youtube o externo",
          "url": "URL de la noticia"
        }
        // ... y así para TODAS las noticias
      ]
    }

    **INSTRUCCIONES OBLIGATORIAS:**
    1. La lista 'news' DEBE contener TODAS las noticias que se te presentan. No omitas ninguna.
    2. Cada noticia DEBE tener un resumen de al menos 3 renglones (150-200 caracteres).
    3. El 'summary' DEBE mencionar explícitamente cada una de las noticias.
    4. Tu respuesta DEBE ser SOLO el JSON. No añadas texto antes, después o explicaciones.
    5. NO uses comillas simples en el JSON.
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

    user_prompt = f"Noticias del día:\n\n{news_info_text}\n\nGenera el JSON con el resumen general y la lista completa de noticias."

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
            {"role": "user", "content": user_prompt + "\n\nDEVUELVE SOLO EL JSON. LA LISTA 'news' DEBE CONTENER TODAS LAS NOTICIAS."}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
        "max_tokens": 3000  # Aumentado para permitir más noticias
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        # --- MOSTRAR LA RESPUESTA COMPLETA PARA DEPURACIÓN ---
        print(f"\n{'='*60}")
        print("📝 RESPUESTA COMPLETA DE DEEPSEEK:")
        print(f"{'='*60}")
        print(ai_response_content)
        print(f"{'='*60}\n")
        
        # Intentar extraer el JSON
        summary_data = extract_json_from_response(ai_response_content)
        
        if summary_data is None:
            print("❌ No se pudo extraer JSON de la respuesta.")
            # Intento final: buscar cualquier JSON en la respuesta
            try:
                json_match = re.search(r'(\{.*\})', ai_response_content, re.DOTALL)
                if json_match:
                    possible_json = json_match.group(1)
                    summary_data = json.loads(possible_json)
                    print("✅ JSON extraído con expresión regular final.")
                else:
                    summary_data = {"summary": "Error al procesar el resumen.", "news": []}
            except:
                summary_data = {"summary": "Error al procesar el resumen.", "news": []}
        
        # Verificar la estructura
        if 'summary' not in summary_data:
            summary_data['summary'] = "Resumen no disponible."
        if 'news' not in summary_data:
            summary_data['news'] = []
        
        # Verificar que la lista 'news' tenga al menos MIN_NEWS_TOTAL noticias
        if len(summary_data.get('news', [])) < MIN_NEWS_TOTAL:
            print(f"⚠️ La lista 'news' solo tiene {len(summary_data.get('news', []))} noticias. Se esperaban al menos {MIN_NEWS_TOTAL}.")
            # Si faltan noticias, añadir las que faltan desde selected_news
            existing_titles = [item.get('title') for item in summary_data.get('news', [])]
            for item in selected_news:
                if item.get('title') not in existing_titles:
                    summary_data['news'].append({
                        'title': item.get('title', 'Sin título'),
                        'resumen': item.get('resumen', 'Noticia destacada')[:300],
                        'fuente': item.get('fuente', 'Fuente desconocida'),
                        'tipo': item.get('tipo', 'externo'),
                        'url': item.get('url', '#')
                    })
                    print(f"✅ Añadida noticia faltante: {item.get('title')}")
        
        # Verificar longitud de resúmenes
        for item in summary_data.get('news', []):
            if len(item.get('resumen', '')) < 150:
                if item.get('resumen', ''):
                    item['resumen'] = item['resumen'] + " Este tema es relevante para el sector tecnológico y la innovación en inteligencia artificial."
        
        # Guardar en caché si es válido
        if summary_data.get('summary') != "Error al procesar el resumen.":
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