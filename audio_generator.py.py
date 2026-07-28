# audio_generator.py
import os
import subprocess
import json

def generate_audio(summary_text, output_filename="resumen_ia.mp3"):
    """Genera un archivo de audio a partir de un texto usando Edge TTS."""
    if not summary_text:
        print("No hay texto para generar audio.")
        return None

    # Edge TTS usa la línea de comandos. Asegúrate de que 'edge-tts' esté instalado.
    # Si no, instálalo con: pip install edge-tts
    # Esta es una alternativa a la librería 'edge_tts' mencionada antes.
    command = [
        "edge-tts",
        "--text", summary_text,
        "--voice", "es-ES-ElviraNeural", # Voz en español
        "--write-media", output_filename
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Audio generado exitosamente: {output_filename}")
        return output_filename
    except FileNotFoundError:
        print("Error: 'edge-tts' no está instalado. Instálalo con 'pip install edge-tts'")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error al generar el audio: {e.stderr}")
        return None

# Función de prueba
if __name__ == '__main__':
    test_text = "Este es un resumen de prueba de las noticias de IA de hoy. Se han anunciado nuevos modelos y se han discutido las implicaciones éticas."
    generate_audio(test_text, "test.mp3")