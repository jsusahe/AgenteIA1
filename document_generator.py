# document_generator.py
import json
import os
from datetime import datetime

def generate_html_document(summary_data, audio_filename, output_filename="index.html"):
    date_str = datetime.now().strftime("%A, %d de %B de %Y")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    AUDIO_FILE = "resumen_ia.mp3"
    print(f"🔊 Audio para HTML: {AUDIO_FILE}")
    
    # --- Generar enlaces al histórico CON DEPURACIÓN ---
    history_links = ""
    history_folder = "historial"
    
    print(f"📁 Ruta absoluta de la carpeta: {os.path.abspath(history_folder)}")
    print(f"📁 ¿Existe la carpeta? {os.path.exists(history_folder)}")
    
    if os.path.exists(history_folder):
        print(f"📁 Contenido de la carpeta: {os.listdir(history_folder)}")
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
        
        html_files.sort(key=lambda x: x[0], reverse=True)
        print(f"📊 Total de archivos históricos encontrados: {len(html_files)}")
        
        for file_date, filename in html_files:
            if file_date.strftime("%Y-%m-%d") != current_date:
                display_date = file_date.strftime("%d/%m/%Y")
                history_links += f'<li><a href="historial/{filename}">{display_date}</a></li>'
                print(f"   🔗 Enlace generado: historial/{filename} -> {display_date}")
    else:
        print("⚠️ Carpeta 'historial' NO encontrada.")
    
    # --- Crear la sección de histórico SIEMPRE ---
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
    
    # --- Construir el HTML completo (el resto del código es igual) ---
    # ... (mantén el resto del HTML sin cambios) ...