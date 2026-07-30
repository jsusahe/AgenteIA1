# summary_generator.py
import json
import requests
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# --- CONFIGURACIÓN ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
# ---------------------

def generate_summary(news_items):
    """
    Genera un resumen y una lista de noticias usando DeepSeek.
    Acepta una lista de noticias con diferentes estructuras (YouTube y externas).
    """
    if not news_items:
        print("No hay datos de noticias para resumir.")
        return {"summary": "No se encontraron noticias relevantes hoy.", "news": []}

    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY no está configurada como variable de entorno.")
        return {"summary": "Error de configuración: clave API no encontrada.", "news": []}

    # --- Construir el prompt para DeepSeek ---
    news_info_text = ""
    for i, item in enumerate(news_items):
        # Obtener datos con claves consistentes
        titulo = item.get('title', 'Sin título')
        fuente = item.get('fuente', 'Fuente desconocida')
        resumen = item.get('resumen', '')
        tipo = item.get('tipo', 'desconocido')
        
        # Determinar el contexto según el tipo de fuente
        if tipo == 'youtube':
            contexto = resumen[:500] if resumen else 'Transcripción no disponible'
            etiqueta = "🎥 [YouTube]"
        else:
            contexto = resumen[:500] if resumen else 'Resumen no disponible'
            etiqueta = "📰 [Fuente externa]"
        
        # Agregar al texto del prompt
        news_info_text += f"Noticia {i+1}: {etiqueta}\n"
        news_info_text += f"Título: {titulo}\n"
        news_info_text += f"Fuente: {fuente}\n"
        news_info_text += f"Resumen: {contexto}\n\n"

    system_prompt = """
    Eres un asistente de IA especializado en analizar y resumir noticias sobre tecnología e inteligencia artificial.

    Tu tarea es procesar la información de las siguientes noticias (que pueden venir de videos de YouTube o de fuentes escritas) y generar:

    1. Un **resumen general** en español de 2-3 párrafos que capture las ideas, anuncios y tendencias más importantes del día en el mundo de la IA.
    2. Una lista de **noticias individuales** en formato JSON.

    Para la lista de noticias, cada elemento debe ser un objeto con:
    - 'title': El título de la noticia.
    - 'resumen': Un resumen breve (máximo 2 frases) de la noticia.
    - 'fuente': El nombre de la fuente (ej. "YouTube: EDteam", "TechCrunch").
    - 'tipo': Indica si la noticia viene de 'youtube' o de 'externo'.

    Sé conciso, relevante y enfócate en los hechos y novedades clave para la industria de la IA.
    """

    user_prompt = f"Aquí está la lista de noticias recopiladas del día:\n\n{news_info_text}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-v4-flash",  # Modelo económico y eficiente
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\nGenera tu respuesta en formato JSON con las claves 'summary' (string) y 'news' (lista de objetos con 'title', 'resumen', 'fuente' y 'tipo')."}
        ],
        "response_format": {"type": "json_object"}  # Forzar salida JSON
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_response_content = result['choices'][0]['message']['content']
        
        # Intentar parsear el JSON devuelto por el modelo
        try:
            summary_data = json.loads(ai_response_content)
            # Asegurar que la estructura sea válida
            if 'summary' not in summary_data:
                summary_data['summary'] = "Resumen no disponible."
            if 'news' not in summary_data:
                summary_data['news'] = []
            return summary_data
        except json.JSONDecodeError:
            print(f"❌ Error: El modelo no devolvió un JSON válido. Respuesta: {ai_response_content[:200]}...")
            # Fallback: intentar extraer información básica
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
    
    # Verificar que la clave API está configurada
    if not DEEPSEEK_API_KEY:
        print("⚠️ DEEPSEEK_API_KEY no configurada. Usando datos de ejemplo para prueba.")
    
    # Datos de prueba con estructura mixta (YouTube + externas)
    test_news = [
        {
            "title": "OpenAI anuncia GPT-5 con capacidad de 1M de tokens",
            "resumen": "OpenAI ha presentado oficialmente GPT-5, su nuevo modelo con capacidad de contexto de 1 millón de tokens y mejor rendimiento en razonamiento.",
            "fuente": "YouTube: EDteam",
            "url": "https://www.youtube.com/watch?v=123",
            "tipo": "youtube"
        },
        {
            "title": "Google lanza Gemini Ultra para empresas",
            "resumen": "Google ha anunciado Gemini Ultra, su modelo más avanzado, disponible ahora para clientes empresariales con API dedicada.",
            "fuente": "TechCrunch",
            "url": "https://techcrunch.com/...",
            "tipo": "externo"
        },
        {
            "title": "Anthropic publica su posición sobre modelos abiertos",
            "resumen": "Anthropic ha publicado un documento oficial sobre su postura respecto a los modelos de IA abiertos, generando debate en la comunidad.",
            "fuente": "VentureBeat",
            "url": "https://venturebeat.com/...",
            "tipo": "externo"
        }
    ]
    
    # Generar resumen
    summary = generate_summary(test_news)
    print("\n📊 Resumen generado:")
    print(json.dumps(summary, indent=4, ensure_ascii=False))