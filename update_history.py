# update_history.py
"""
Script para actualizar el index.html con los enlaces al histórico.
Escanea la carpeta 'historial/' y genera los enlaces en el formato correcto.
"""
import os
import re
from datetime import datetime

# --- CONFIGURACIÓN ---
HISTORY_FOLDER = "historial"
INDEX_FILE = "index.html"
# --------------------

def get_history_files():
    """Escanea la carpeta historial y devuelve una lista de archivos HTML con su fecha."""
    if not os.path.exists(HISTORY_FOLDER):
        print(f"❌ Carpeta '{HISTORY_FOLDER}' no encontrada.")
        return []
    
    html_files = []
    for f in os.listdir(HISTORY_FOLDER):
        if f.startswith("resumen_") and f.endswith(".html"):
            try:
                # Extraer fecha del nombre: resumen_YYYY-MM-DD.html
                date_str = f.replace("resumen_", "").replace(".html", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                html_files.append((file_date, f))
                print(f"✅ Encontrado: {f} (fecha: {date_str})")
            except ValueError:
                print(f"⚠️ Formato no reconocido: {f}")
                continue
    
    # Ordenar por fecha (más reciente primero)
    html_files.sort(key=lambda x: x[0], reverse=True)
    return html_files

def generate_history_links(html_files):
    """Genera los enlaces HTML para la sección de histórico."""
    if not html_files:
        return "<li>No hay resúmenes históricos disponibles aún.</li>"
    
    links = ""
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for file_date, filename in html_files:
        # No mostrar el día actual (ya está en el resumen del día)
        if file_date.strftime("%Y-%m-%d") != current_date:
            display_date = file_date.strftime("%d/%m/%Y")
            links += f'<li><a href="historial/{filename}">{display_date}</a></li>\n'
    
    return links if links else "<li>No hay resúmenes históricos disponibles aún.</li>"

def update_index_html():
    """Actualiza el index.html con la sección de histórico."""
    print("🔍 Escaneando archivos históricos...")
    html_files = get_history_files()
    
    if not html_files:
        print("⚠️ No se encontraron archivos históricos.")
        return False
    
    print(f"📊 Total de archivos encontrados: {len(html_files)}")
    
    # Generar los enlaces
    history_links = generate_history_links(html_files)
    
    # Construir la sección de histórico completa
    history_section = f"""
    <h2>📚 Histórico de Resúmenes</h2>
    <ul>
        {history_links}
    </ul>
    <p><i>Mostrando hasta los últimos 10 días. Los más antiguos se archivan automáticamente.</i></p>
    """
    
    # Leer el index.html actual
    if not os.path.exists(INDEX_FILE):
        print(f"❌ No se encontró {INDEX_FILE}. Ejecuta main.py primero.")
        return False
    
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar la sección de histórico actual y reemplazarla
    pattern = r'(<h2>📚 Histórico de Resúmenes</h2>.*?<hr>)'
    
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Reemplazar la sección existente
        new_content = content.replace(match.group(1), history_section + "\n        <hr>")
        print("✅ Sección de histórico actualizada.")
    else:
        # Si no existe, insertarla antes del pie de página
        footer_pattern = r'(<hr>\s*<div class="footer">)'
        footer_match = re.search(footer_pattern, content, re.DOTALL)
        if footer_match:
            new_content = content.replace(footer_match.group(1), history_section + "\n        " + footer_match.group(1))
            print("✅ Sección de histórico añadida.")
        else:
            print("❌ No se pudo encontrar el lugar para insertar la sección.")
            return False
    
    # Guardar el nuevo index.html
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ {INDEX_FILE} actualizado correctamente.")
    print("📁 Archivos históricos encontrados:")
    for file_date, filename in html_files:
        print(f"   - {filename} ({file_date.strftime('%d/%m/%Y')})")
    
    return True

# --- Función principal ---
if __name__ == '__main__':
    print("="*60)
    print("🔄 ACTUALIZADOR DE HISTÓRICO PARA INDEX.HTML")
    print("="*60)
    
    print(f"📁 Directorio actual: {os.getcwd()}")
    print(f"📁 Carpeta de histórico: {os.path.abspath(HISTORY_FOLDER)}")
    
    success = update_index_html()
    
    if success:
        print("\n✅ Proceso completado.")
        print("💡 Abre index.html en tu navegador para ver los cambios.")
    else:
        print("\n❌ El proceso falló. Revisa los mensajes de error.")