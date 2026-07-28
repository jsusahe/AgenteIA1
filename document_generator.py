# document_generator.py
import json
from datetime import datetime

def generate_html_document(summary_data, audio_filename, output_filename="index.html"):
    """Genera un documento HTML con el resumen, las noticias y un enlace al audio."""
    date_str = datetime.now().strftime("%A, %d de %B de %Y")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Noticias IA - {date_str}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; line-height: 1.6; max-width: 800px; margin: 20px auto; padding: 0 20px; color: #333; background-color: #f9f9f9; }}
            h1, h2 {{ color: #0056b3; }}
            .summary {{ background-color: #e9f0f9; padding: 15px 20px; border-radius: 8px; border-left: 5px solid #0056b3; margin-bottom: 30px; }}
            .news-item {{ background-color: white; padding: 10px 15px; margin-bottom: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 3px solid #17a2b8; }}
            .news-item .source {{ font-size: 0.9em; color: #6c757d; margin-top: 5px; }}
            .audio-player {{ margin: 20px 0; padding: 15px; background-color: #f1f3f5; border-radius: 8px; text-align: center; }}
            hr {{ border: 0; height: 1px; background: #ddd; margin: 30px 0; }}
            .footer {{ font-size: 0.8em; color: #6c757d; text-align: center; margin-top: 40px; }}
        </style>
    </head>
    <body>
        <h1>🤖 Boletín Diario de Inteligencia Artificial</h1>
        <p><strong>Fecha:</strong> {date_str}</p>

        <h2>📝 Resumen del Día</h2>
        <div class="summary">
            <p>{summary_data.get('summary', 'No se pudo generar el resumen.')}</p>
        </div>

        <h2>📰 Novedades Destacadas</h2>
        <div id="news-list">
    """

    for item in summary_data.get('news', []):
        html_content += f"""
            <div class="news-item">
                <strong>{item.get('titulo', 'Sin título')}</strong>
                <p>{item.get('resumen', 'Sin resumen disponible.')}</p>
                <div class="source">🎥 Fuente: {item.get('fuente', 'YouTube')}</div>
            </div>
        """

    html_content += f"""
        </div>
        <h2>🎧 Resumen en Audio</h2>
        <div class="audio-player">
            <audio controls style="width: 100%;">
                <source src="{audio_filename}" type="audio/mpeg">
                Tu navegador no soporta el elemento de audio.
            </audio>
            <p><a href="{audio_filename}" download>Descargar audio</a></p>
        </div>
        <hr>
        <div class="footer">
            <p>Generado automáticamente por el Agente IA de EBS. 
            <br><a href="https://github.com/tu-usuario/mi_agente_ia">Ver código en GitHub</a></p>
        </div>
    </body>
    </html>
    """
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Documento HTML generado: {output_filename}")
    return output_filename

if __name__ == '__main__':
    # Datos de prueba
    test_data = {
        "summary": "Hoy se han conocido importantes novedades en el mundo de la IA. OpenAI ha presentado nuevas funciones para ChatGPT mientras se discuten sus implicaciones.",
        "news": [
            {"titulo": "OpenAI anuncia ChatGPT Work", "resumen": "Una nueva suite para empresas con herramientas de productividad.", "fuente": "EDteam"},
            {"titulo": "Nuevos modelos de lenguaje", "resumen": "Se han lanzado modelos con capacidad de contexto de 1M de tokens.", "fuente": "XavierMitjana"}
        ]
    }
    generate_html_document(test_data, "test_audio.mp3", "test_index.html")