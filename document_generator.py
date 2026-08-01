# document_generator.py
import json
import os
from datetime import datetime

def generate_html_document(summary_data, audio_filename, output_filename="index.html"):
    """
    Genera un documento HTML con el resumen, las noticias y un enlace al audio.
    AHORA SIEMPRE INCLUYE LA SECCIÓN DE HISTÓRICO.
    """
    date_str = datetime.now().strftime("%A, %d de %B de %Y")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Forzar el uso de resumen_ia.mp3 para el reproductor
    AUDIO_FILE = "resumen_ia.mp3"
    print(f"🔊 Audio para HTML: {AUDIO_FILE}")
    
    # --- Generar enlaces al histórico ---
    history_links = ""
    history_folder = "historial"
    
    # Depuración: verificar si la carpeta existe
    print(f"📁 Verificando carpeta de histórico: {history_folder}")
    if os.path.exists(history_folder):
        print(f"✅ Carpeta '{history_folder}' encontrada.")
        html_files = []
        for f in os.listdir(history_folder):
            print(f"   Archivo encontrado: {f}")
            if f.startswith("resumen_") and f.endswith(".html"):
                try:
                    date_str_file = f.replace("resumen_", "").replace(".html", "")
                    file_date = datetime.strptime(date_str_file, "%Y-%m-%d")
                    html_files.append((file_date, f))
                    print(f"      ✅ Fecha válida: {date_str_file}")
                except ValueError:
                    print(f"      ⚠️ Formato de fecha no reconocido: {f}")
                    continue
        
        # Ordenar por fecha (más reciente primero)
        html_files.sort(key=lambda x: x[0], reverse=True)
        print(f"📊 Total de archivos históricos encontrados: {len(html_files)}")
        
        for file_date, filename in html_files:
            if file_date.strftime("%Y-%m-%d") != current_date:
                display_date = file_date.strftime("%d/%m/%Y")
                history_links += f'<li><a href="historial/{filename}">{display_date}</a></li>'
                print(f"   🔗 Enlace generado: historial/{filename} -> {display_date}")
    else:
        print(f"⚠️ Carpeta '{history_folder}' NO encontrada.")
    
    # --- Crear la sección de histórico SIEMPRE, incluso si está vacía ---
    if history_links:
        history_section = f"""
        <h2>📚 Histórico de Resúmenes</h2>
        <ul>
            {history_links}
        </ul>
        <p><i>Mostrando hasta los últimos 10 días. Los más antiguos se archivan automáticamente.</i></p>
        """
    else:
        history_section = f"""
        <h2>📚 Histórico de Resúmenes</h2>
        <ul>
            <li>No hay resúmenes históricos disponibles aún.</li>
        </ul>
        <p><i>Los resúmenes se archivarán automáticamente a partir de mañana.</i></p>
        """
    
    # --- Construir el HTML completo ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Noticias IA - {date_str}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 20px auto;
                padding: 0 20px;
                color: #333;
                background-color: #f9f9f9;
            }}
            h1, h2 {{ color: #0056b3; }}
            .summary {{
                background-color: #e9f0f9;
                padding: 15px 20px;
                border-radius: 8px;
                border-left: 5px solid #0056b3;
                margin-bottom: 30px;
            }}
            .news-item {{
                background-color: white;
                padding: 10px 15px;
                margin-bottom: 15px;
                border-radius: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border-left: 3px solid #17a2b8;
            }}
            .news-item .source {{
                font-size: 0.9em;
                color: #6c757d;
                margin-top: 5px;
            }}
            .news-item .source a {{
                color: #0056b3;
                text-decoration: none;
            }}
            .news-item .source a:hover {{
                text-decoration: underline;
            }}
            .audio-player {{
                margin: 20px 0;
                padding: 15px;
                background-color: #f1f3f5;
                border-radius: 8px;
                text-align: center;
            }}
            .history {{
                margin: 30px 0;
                padding: 15px;
                background-color: #eef;
                border-radius: 8px;
            }}
            .history ul {{
                list-style: none;
                padding: 0;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }}
            .history li {{
                background: white;
                padding: 5px 15px;
                border-radius: 20px;
                border: 1px solid #0056b3;
            }}
            .history a {{
                text-decoration: none;
                color: #0056b3;
            }}
            .history a:hover {{
                text-decoration: underline;
            }}
            hr {{
                border: 0;
                height: 1px;
                background: #ddd;
                margin: 30px 0;
            }}
            .footer {{
                font-size: 0.8em;
                color: #6c757d;
                text-align: center;
                margin-top: 40px;
            }}
            @media (max-width: 600px) {{
                body {{ padding: 0 10px; }}
                .history ul {{ flex-direction: column; gap: 5px; }}
            }}
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
        titulo = item.get('title', item.get('titulo', 'Sin título'))
        resumen = item.get('resumen', 'Sin resumen disponible.')
        fuente = item.get('fuente', 'Fuente desconocida')
        url = item.get('url', '#')
        
        link_html = ""
        if url and url != '#':
            link_html = f' - <a href="{url}" target="_blank" rel="noopener noreferrer">🔗 Ver fuente</a>'
        
        html_content += f"""
            <div class="news-item">
                <strong>{titulo}</strong>
                <p>{resumen}</p>
                <div class="source">
                    🎥 Fuente: {fuente}
                    {link_html}
                </div>
            </div>
        """

    if not summary_data.get('news', []):
        html_content += """
            <div class="news-item">
                <p>No se encontraron novedades destacadas para hoy.</p>
            </div>
        """

    html_content += f"""
        </div>

        <h2>🎧 Resumen en Audio</h2>
        <div class="audio-player">
            <audio controls style="width: 100%;">
                <source src="{AUDIO_FILE}" type="audio/mpeg">
                Tu navegador no soporta el elemento de audio.
            </audio>
            <p><a href="{AUDIO_FILE}" download>Descargar audio</a></p>
        </div>

        {history_section}

        <hr>
        <div class="footer">
            <p>Generado automáticamente por el Agente IA de EBS.</p>
            <p>
                <a href="https://github.com/tu-usuario/mi_agente_ia">Ver código en GitHub</a> | 
                <a href="https://github.com/tu-usuario/mi_agente_ia/issues">Reportar un problema</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"📄 Documento HTML generado: {output_filename}")
    return output_filename

# --- Función para pruebas ---
if __name__ == '__main__':
    test_data = {
        "summary": "Hoy se han conocido importantes novedades en el mundo de la IA.",
        "news": [
            {
                "title": "OpenAI anuncia ChatGPT Work",
                "resumen": "Una nueva suite para empresas con herramientas de productividad.",
                "fuente": "EDteam",
                "url": "https://www.youtube.com/watch?v=ejemplo"
            }
        ]
    }
    
    # Crear una carpeta historial de prueba
    if not os.path.exists("historial"):
        os.makedirs("historial")
        # Crear un archivo de prueba
        with open("historial/resumen_2026-07-30.html", "w") as f:
            f.write("<h1>Prueba histórica</h1>")
    
    print("=== Probando document_generator.py ===")
    generate_html_document(test_data, "resumen_ia.mp3", "test_index.html")
    print("\n✅ Archivo test_index.html generado. Ábrelo para ver los enlaces al histórico.")