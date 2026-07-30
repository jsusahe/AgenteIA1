# news_fetcher.py
import feedparser
import requests
import json
from datetime import datetime, timedelta
import os
import time
from typing import List, Dict
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# --- CONFIGURACIÓN ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

MAX_ARTICLES_PER_SOURCE = 5  # Número máximo de artículos a extraer por fuente
DAYS_BACK = 2  # Buscar noticias de los últimos 2 días
TOP_NEWS_LIMIT = 10  # Número de noticias a seleccionar como las más relevantes

# --- LISTA DE FUENTES RSS (50+ altamente relevantes) ---
# Fuentes de noticias generales y de tecnología
RSS_FEEDS = [
    # Generales y tecnología
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.technologyreview.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://feeds.feedburner.com/ArsTechnica/Technology-Lab",
    "https://www.theverge.com/rss/tech/index.xml",
    "https://www.wired.com/feed/category/ideas/latest/rss",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.reuters.com/technology/",
    
    # Especializadas en IA
    "https://www.artificialintelligence-news.com/feed/",
    "https://syncedreview.com/feed/",
    "https://the-decoder.com/feed/",
    "https://www.aitimejournal.com/feed",
    "https://thegradient.pub/feed/",
    "https://www.unite.ai/feed/",
    "https://www.analyticsvidhya.com/feed/",
    "https://www.kdnuggets.com/feed",
    "https://www.datasciencecentral.com/feed",
    "https://www.oreilly.com/radar/feed/",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
    
    # En español
    "https://feeds.elpais.com/mrss-s/pages/ep/site/el pais.com/portada",
    "https://www.bbc.com/mundo/ciencia/",
    "https://www.infobae.com/tecnologia/",
    "https://www.xataka.com/",
    "https://www.microsiervos.com/feeds/",
    
    # Investigación y desarrollo
    "https://huggingface.co/blog/feed.xml",
    "https://arxiv.org/list/cs.AI/recent?rss=1",
    "https://arxiv.org/list/cs.LG/recent?rss=1",
    "https://paperswithcode.com/rss",
    "https://www.deepmind.com/blog/feed",
    "https://ai.googleblog.com/feeds/posts/default",
    "https://openai.com/blog/rss",
    "https://www.anthropic.com/blog",
    "https://ai.meta.com/blog/",
    "https://deepseek.com/",
    "https://www.microsoft.com/en-us/ai/ai-news",
    "https://research.ibm.com/blog/feed",
    "https://www.amazon.science/blog",
    "https://www.salesforce.com/blog/category/ai/",
    "https://www.nvidia.com/en-us/ai-data-science/",
    
    # Agregadores y rankings
    "https://hnrss.org/frontpage",
    "https://github.com/trending",
    "https://ai.doocs.org/",
    "https://www.aibase.com/",
    "https://aitop100.cn",
    
    # Empresas emergentes y productos
    "https://www.producthunt.com/feed?tag=artificial-intelligence",
    "https://www.techmeme.com/feed",
    "https://www.siliconangle.com/feed/",
    "https://www.theregister.com/ai/headlines.atom",
    "https://www.cnet.com/rss/news/ai/",
    "https://www.forbes.com/ai/feed/",
    "https://www.fastcompany.com/feed/technology",
    "https://www.businessinsider.com/artificial-intelligence",
    
    # Ética y regulación
    "https://www.eff.org/rss/updates.xml",
    "https://www.adalovelaceinstitute.org/feed/",
    "https://www.weforum.org/feed/agenda/artificial-intelligence",
    "https://www.itu.int/en/Pages/rss.aspx",
]

def fetch_news_from_rss(feed_url: str) -> List[Dict]:
    """Obtiene los titulares y enlaces de un feed RSS."""
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)

        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            # Intentar obtener la fecha de publicación
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                pub_date = datetime(*published[:6])
                if pub_date < cutoff_date:
                    continue  # Saltar noticias antiguas

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
    """Consulta todas las fuentes RSS y recopila noticias."""
    print("📰 Recopilando noticias de fuentes externas...")
    all_articles = []
    for feed_url in RSS_FEEDS:
        print(f"  Consultando: {feed_url}")
        articles = fetch_news_from_rss(feed_url)
        all_articles.extend(articles)
        time.sleep(0.5)  # Pequeña pausa para no sobrecargar los servidores
    print(f"✅ Total de noticias recopiladas: {len(all_articles)}")
    return all_articles

def select_top_news(articles: List[Dict], limit: int = TOP_NEWS_LIMIT) -> List[Dict]:
    """
    Utiliza DeepSeek para seleccionar las noticias más relevantes para la industria de la IA.
    Si la API falla, devuelve las primeras 'limit' noticias.
    """
    if not articles:
        return []

    if not DEEPSEEK_API_KEY:
        print("⚠️ DEEPSEEK_API_KEY no configurada. Devolviendo primeras noticias.")
        return articles[:limit]

    print(f"🧠 Seleccionando las {limit} noticias más relevantes con DeepSeek...")

    # Crear un resumen de las noticias para enviar a DeepSeek
    news_summary = ""
    for i, article in enumerate(articles):
        news_summary += f"{i+1}. Título: {article['title']}\n"
        news_summary += f"   Fuente: {article['source']}\n"
        news_summary += f"   Resumen: {article['summary'][:200]}...\n\n"

    system_prompt = """
    Eres un editor de noticias especializado en inteligencia artificial.
    Tu tarea es analizar una lista de noticias y seleccionar las 10 más relevantes para la industria de la IA.
    Criterios de selección:
    - Novedad: Noticias sobre lanzamientos, avances o eventos recientes.
    - Impacto: Noticias que pueden afectar a la industria, empresas o usuarios.
    - Relevancia: Noticias sobre modelos, aplicaciones, regulación o figuras clave de la IA.
    - Diversidad: Intenta cubrir diferentes áreas (investigación, productos, política, etc.).
    Devuelve SOLO una lista JSON con los índices de las noticias seleccionadas (1-based), sin ningún otro texto.
    Ejemplo: {"indices": [1, 3, 5, 8, 12, 15, 18, 20, 22, 25]}
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
        
        # Parsear la respuesta JSON
        try:
            selected_data = json.loads(ai_response)
            selected_indices = selected_data.get('indices', [])
        except json.JSONDecodeError:
            print(f"⚠️ Error al parsear respuesta JSON: {ai_response[:100]}")
            return articles[:limit]
        
        # Asegurarse de que los índices son válidos
        selected_articles = []
        for idx in selected_indices[:limit]:
            if 1 <= idx <= len(articles):
                selected_articles.append(articles[idx-1])
        
        print(f"✅ Seleccionadas {len(selected_articles)} noticias.")
        return selected_articles

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al seleccionar noticias con DeepSeek: {e}")
        # Fallback: devolver las primeras 'limit' noticias
        return articles[:limit]

def get_top_news(limit: int = TOP_NEWS_LIMIT) -> List[Dict]:
    """Función principal que obtiene y selecciona las mejores noticias."""
    all_news = fetch_all_news()
    if not all_news:
        return []
    top_news = select_top_news(all_news, limit)
    return top_news

# --- Función para pruebas ---
if __name__ == '__main__':
    print("=== Probando news_fetcher.py ===")
    
    # Probar solo la recopilación (si no hay clave API)
    if not DEEPSEEK_API_KEY:
        print("\n⚠️ DEEPSEEK_API_KEY no configurada. Probando solo recopilación...")
        all_news = fetch_all_news()
        print(f"\n📊 Total de noticias recopiladas: {len(all_news)}")
        print("\nPrimeras 5 noticias:")
        for i, article in enumerate(all_news[:5], 1):
            print(f"{i}. {article['title']} ({article['source']})")
    else:
        # Probar flujo completo
        top = get_top_news(5)
        print("\n📊 Top noticias seleccionadas:")
        for i, article in enumerate(top, 1):
            print(f"{i}. {article['title']} ({article['source']})")