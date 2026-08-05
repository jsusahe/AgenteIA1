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

def generate_summary_fallback(selected_news):
    """Genera un resumen básico TRADUCIDO cuando DeepSeek falla."""
    print("🔄 Usando modo de respaldo: generando resumen básico...")
    
    summary_text = "Resumen del día (generado automáticamente por el agente):\n\n"
    for i, item in enumerate(selected_news[:7]):
        titulo = item.get('title', 'Sin título')
        fuente = item.get('fuente', 'Fuente desconocida')
        resumen = item.get('resumen', '')
        summary_text += f"{i+1}. {titulo}\n   Fuente: {fuente}\n   {resumen[:200]}...\n\n"
    
    return {
        "summary": summary_text,
        "news": [
            {
                'title': item.get('title', 'Sin título'),
                'resumen': item.get('resumen', 'Noticia destacada')[:300],
                'fuente': item.get('fuente', 'Fuente desconocida'),
                'tipo': item.get('tipo', 'externo'),
                'url': item.get('url', '#')
            }
            for item in selected_news[:7]
        ]
    }

def extract_json_robust(text):
    """
    Extrae JSON de la respuesta de DeepSeek de forma robusta.
    """
    # Buscar el JSON completo
    json_pattern = r'(\{[\s\S]*"summary"[\s\S]*"news"[\s\S]*\})'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
        # Intentar reparar el JSON si está incompleto
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Si falla, intentar cerrar el JSON
            if not json_str.endswith('}'):
                json_str += '}'
            try:
                return json.loads(json_str)
            except:
                pass
    
    # Si no se encuentra, buscar cualquier objeto JSON
    json_pattern2 = r'(\{[^{}]*"summary"[^{}]*"news"[^{}]*\})'
    match = re.search(json_pattern2, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Si falla, construir JSON básico desde el texto
    print("⚠️ No se pudo extraer JSON completo. Intentando construir desde texto...")
    # Buscar el summary
    summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', text)
    summary_text = summary_match.group(1) if summary_match else "Resumen no disponible."
    
    # Buscar noticias
    news_items = []
    title_pattern = r'"title"\s*:\s*"([^"]*)"'
    titles = re.findall(title_pattern, text)
    for i, title in enumerate(titles[:7]):
        news_items.append({
            'title': title,
            'resumen': 'Noticia destacada del día.',
            'fuente': 'Fuente externa',
            'tipo': 'externo',
            'url': '#'
        })
    
    return {
        "summary": summary_text,
        "news": news_items if news_items else []
    }

def generate_summary(news_items):
    if not news_items:
        print("No hay datos de noticias para resumir.")
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada.")
        return generate_summary_fallback(news_items[:7])

    print("\n🔍 Seleccionando noticias representativas...")
    selected_news = select_representative_news(news_items)
    
    if not selected_news:
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    # --- Prompt mejorado para forzar JSON ---
    system_prompt = """
    Eres un asistente que resume noticias de IA. **DEBES** generar un JSON válido con la siguiente estructura EXACTA:

    {
      "summary": "Resumen general en español (3-4 párrafos) que mencione TODAS las noticias listadas.",
      "news": [
        {
          "title": "Título de la noticia 1 (TRADUCIDO al español)",
          "resumen": "Resumen extenso de la noticia 1 en español (mínimo 3 renglones)",
          "fuente": "Nombre de la fuente",
          "tipo": "youtube o externo",
          "url": "URL de la noticia"
        },
        {
          "title": "Título de la noticia 2 (TRADUCIDO al español)",
          "resumen": "Resumen extenso de la noticia 2 en español (mínimo 3 renglones)",
          "fuente": "Nombre de la fuente",
          "tipo": "youtube o externo",
          "url": "URL de la noticia"
        }
        // ... y así para TODAS las noticias
      ]
    }

    **INSTRUCCIONES OBLIGATORIAS:**
    1. La lista 'news' DEBE contener TODAS las noticias que se te presentan. No omitas ninguna.
    2. Los TÍTULOS de las noticias DEBEN estar TRADUCIDOS al español.
    3. Tu respuesta DEBE ser SOLO el JSON. No añadas texto antes, después o explicaciones.
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
        news_info_text += f"Título original: {titulo}\n"
        news_info_text += f"Fuente: {fuente}\n"
        news_info_text += f"URL: {url}\n"
        news_info_text += f"Resumen: {contexto}\n\n"

    user_prompt = f"Noticias del día (debes traducir los títulos al español):\n\n{news_info_text}\n\nGenera el JSON con el resumen general y la lista completa de noticias con títulos en español."

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
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
        "max_tokens": 5000  # Aumentado para evitar cortes
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        print(f"\n📝 Respuesta de DeepSeek (primeros 500 caracteres): {ai_response_content[:500]}...")
        
        # Intentar extraer el JSON de forma robusta
        summary_data = extract_json_robust(ai_response_content)
        
        # Verificar la estructura
        if 'summary' not in summary_data:
            summary_data['summary'] = "Resumen no disponible."
        if 'news' not in summary_data:
            summary_data['news'] = []
        
        # Verificar que la lista 'news' tenga al menos MIN_NEWS_TOTAL noticias
        if len(summary_data.get('news', [])) < MIN_NEWS_TOTAL:
            print(f"⚠️ La lista 'news' solo tiene {len(summary_data.get('news', []))} noticias. Añadiendo faltantes...")
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
        
        # Guardar en caché
        cache[cache_key] = summary_data
        save_cache(cache)
        
        return summary_data
        
    except requests.exceptions.Timeout:
        print("❌ Timeout al llamar a DeepSeek. Usando modo de respaldo.")
        return generate_summary_fallback(selected_news)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return generate_summary_fallback(selected_news)

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