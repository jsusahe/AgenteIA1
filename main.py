# main.py
import os
import json
from datetime import datetime
from youtube_fetcher import fetch_all_youtube_content
from summary_generator import generate_summary
from audio_generator import generate_audio
from document_generator import generate_html_document
from drive_uploader import upload_daily_document

def run_agent():
    print(f"--- Iniciando Agente IA - {datetime.now()} ---")

    # 1. Obtener contenido de YouTube
    videos = fetch_all_youtube_content()
    if not videos:
        print("No se encontraron videos nuevos. Saliendo.")
        # Podrías generar un documento que diga "Sin novedades hoy"
        return

    # 2. Generar resumen con DeepSeek
    summary_data = generate_summary(videos)
    print("Resumen generado.")

    # 3. Generar Audio
    summary_text = summary_data.get('summary', '')
    audio_file = generate_audio(summary_text, "resumen_ia.mp3")

    # 4. Generar Documento HTML
    html_file = generate_html_document(summary_data, audio_file or "audio_no_disponible.mp3", "index.html")

    # 5. Subir a Google Drive
    upload_daily_document(html_file, audio_file)

    print(f"--- Agente IA finalizado - {datetime.now()} ---")

if __name__ == '__main__':
    run_agent()
