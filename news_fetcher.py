# news_fetcher.py
import feedparser
import requests
import json
from datetime import datetime, timedelta
import os
import time
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

MAX_ARTICLES_PER_SOURCE = 3  # REDUCIDO de 5 a 3 para ahorrar tokens
DAYS_BACK = 2
TOP_NEWS_LIMIT = 5  # REDUCIDO de 10 a 5

RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://feeds.feedburner.com/ArsTechnica/Technology-Lab",
    "https://www.theverge.com/rss/tech/index.xml",
    # ... (mantén el resto de las fuentes)
]

def fetch_news_from_rss(feed_url: str) -> List[Dict]:
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)

        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                pub_date = datetime(*published[:6])
                if pub_date < cutoff_date:
                    continue

            articles.append({
                'title': entry.get('title', 'Sin título'),
                'link': entry.get('link', '#'),
                'summary': entry.get('summary', ''),
                'source': feed.feed.get('title', 'Fuente desconocida'),
                'published': published
            })
        return articles
    except Exception as e:
        print(f"⚠️ Error al consultar {feed_url}: {e}")
        return []

def fetch_all_news() -> List[Dict]:
    print("📰 Recopilando noticias de fuentes externas...")
    all_articles = []
    for feed_url in RSS_FEEDS:
        print(f"  Consultando: {feed_url}")
        articles = fetch_news_from_rss(feed_url)
        all_articles.extend(articles)
        time.sleep(0.5)
    print(f"✅ Total de noticias recopiladas: {len(all_articles)}")
    return all_articles

def select_top_news(articles: List[Dict], limit: int = TOP_NEWS_LIMIT) -> List[Dict]:
    if not articles:
        return []

    if not DEEPSEEK_API_KEY:
        print("⚠️ DEEPSEEK_API_KEY no configurada. Devolviendo primeras noticias.")
        return articles[:limit]

    print(f"🧠 Seleccionando las {limit} noticias más relevantes con DeepSeek...")

    news_summary = ""
    for i, article in enumerate(articles):
        news_summary += f"{i+1}. Título: {article['title']}\n"
        news_summary += f"   Fuente: {article['source']}\n"
        news_summary += f"   Resumen: {article['summary'][:200]}...\n\n"

    system_prompt = """
    Eres un editor de noticias especializado en inteligencia artificial.
    Tu tarea es analizar una lista de noticias y seleccionar las 5 más relevantes para la industria de la IA.
    Criterios de selección:
    - Novedad: Noticias sobre lanzamientos, avances o eventos recientes.
    - Impacto: Noticias que pueden afectar a la industria, empresas o usuarios.
    - Relevancia: Noticias sobre modelos, aplicaciones, regulación o figuras clave de la IA.
    - Diversidad: Intenta cubrir diferentes áreas (investigación, productos, política, etc.).
    Devuelve SOLO una lista JSON con los índices de las noticias seleccionadas (1-based).
    Ejemplo: {"indices": [1, 3, 5, 8, 12]}
    """

    user_prompt = f"Aquí está la lista de noticias recopiladas:\n\n{news_summary}\n\nSelecciona los índices de las {limit} noticias más relevantes."

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
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_response = result['choices'][0]['message']['content']
        
        try:
            selected_data = json.loads(ai_response)
            selected_indices = selected_data.get('indices', [])
        except json.JSONDecodeError:
            print(f"⚠️ Error al parsear respuesta JSON: {ai_response[:100]}")
            return articles[:limit]
        
        selected_articles = []
        for idx in selected_indices[:limit]:
            if 1 <= idx <= len(articles):
                selected_articles.append(articles[idx-1])
        
        print(f"✅ Seleccionadas {len(selected_articles)} noticias.")
        return selected_articles

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al seleccionar noticias con DeepSeek: {e}")
        return articles[:limit]

def get_top_news(limit: int = TOP_NEWS_LIMIT) -> List[Dict]:
    all_news = fetch_all_news()
    if not all_news:
        return []
    top_news = select_top_news(all_news, limit)
    return top_news

if __name__ == '__main__':
    print("=== Probando news_fetcher.py ===")
    if not DEEPSEEK_API_KEY:
        print("\n⚠️ DEEPSEEK_API_KEY no configurada. Probando solo recopilación...")
        all_news = fetch_all_news()
        print(f"\n📊 Total de noticias recopiladas: {len(all_news)}")
        print("\nPrimeras 5 noticias:")
        for i, article in enumerate(all_news[:5], 1):
            print(f"{i}. {article['title']} ({article['source']})")
    else:
        top = get_top_news(5)
        print("\n📊 Top noticias seleccionadas:")
        for i, article in enumerate(top, 1):
            print(f"{i}. {article['title']} ({article['source']})")