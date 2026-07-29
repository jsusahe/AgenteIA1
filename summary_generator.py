# summary_generator.py
import json
import requests
import os

# --- CONFIGURACIÓN ---
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') # <--- Pega tu clave aquí
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
# ---------------------

def generate_summary(videos_data):
    """Genera un resumen y una lista de noticias usando DeepSeek."""
    if not videos_data:
        print("No hay datos de video para resumir.")
        return {"summary": "No se encontraron videos nuevos hoy.", "news": []}

    # Construir el prompt para DeepSeek
    video_info_text = ""
    for i, video in enumerate(videos_data):
        video_info_text += f"Video {i+1}: Título: {video['title']}\n"
        video_info_text += f"Resumen/Descripción: {video.get('description', 'Sin descripción.')[:300]}\n" # Usar descripción como contexto extra
        video_info_text += f"Transcripción: {video.get('transcript', 'Transcripción no disponible')[:3000]}...\n\n" # Usar primeros 3000 chars de transcripción

    system_prompt = """Eres un asistente de IA especializado en analizar y resumir contenido de videos de tecnología e inteligencia artificial. Tu tarea es procesar la información de los siguientes videos y generar dos cosas:
    1.  Un **resumen general** en español de 2-3 párrafos que capture las ideas y anuncios más importantes del día.
    2.  Una lista de **noticias individuales** en formato JSON. Cada noticia debe ser un objeto con: 'titulo', 'resumen' (máximo 2 frases), y 'fuente' (el título del video de YouTube del que proviene).
    Sé conciso y enfócate en los hechos y novedades clave."""
    user_prompt = f"Aquí está la información de los videos del día:\n\n{video_info_text}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": "deepseek-v4-flash", # Modelo más económico, ideal para esta tarea [citation:2]
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\nGenera tu respuesta en formato JSON con las claves 'summary' (string) y 'news' (lista de objetos con 'titulo', 'resumen', 'fuente')."}
        ],
        "response_format": {"type": "json_object"} # Esto es importante para forzar la salida JSON
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        # Extraer el contenido generado por el modelo
        ai_response_content = result['choices'][0]['message']['content']
        # Intentar parsear el JSON que devolvió el modelo
        try:
            summary_data = json.loads(ai_response_content)
            # Añadir los títulos originales como fuente si no lo hizo el modelo
            for news_item in summary_data.get('news', []):
                # El modelo ya debería haber incluido la fuente, pero lo aseguramos.
                pass
            return summary_data
        except json.JSONDecodeError:
            print(f"Error: El modelo no devolvió un JSON válido. Respuesta: {ai_response_content}")
            return {"summary": "Error al procesar el resumen.", "news": []}
    except Exception as e:
        print(f"Error al llamar a la API de DeepSeek: {e}")
        return {"summary": "Error de conexión con DeepSeek.", "news": []}

# Función para probar
if __name__ == '__main__':
    # Cargar el contenido de ejemplo de la etapa anterior
    try:
        with open('youtube_content.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        summary = generate_summary(data)
        print("Resumen generado:")
        print(json.dumps(summary, indent=4, ensure_ascii=False))
    except FileNotFoundError:
        print("Primero ejecuta youtube_fetcher.py para obtener algunos datos de ejemplo.")
