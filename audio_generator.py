# audio_generator.py
import os
import subprocess
import json

def generate_audio(summary_text, output_filename="resumen_ia.mp3"):
    """
    Genera un archivo de audio a partir de un texto usando Edge TTS.
    Limita la duración a aproximadamente 60 segundos (150 palabras).
    """
    if not summary_text:
        print("No hay texto para generar audio.")
        return None

    # --- LIMITAR EL TEXTO A ~150 PALABRAS (60 SEGUNDOS) ---
    # Edge TTS lee aprox 2-3 palabras por segundo, 150 palabras = ~60 segundos
    words = summary_text.split()
    original_word_count = len(words)
    
    if len(words) > 150:
        # Cortar en la última oración completa dentro del límite
        summary_text = " ".join(words[:150])
        # Intentar cortar en un punto o coma para no cortar a medias
        last_period = summary_text.rfind('.')
        last_comma = summary_text.rfind(',')
        last_question = summary_text.rfind('?')
        last_exclamation = summary_text.rfind('!')
        cut_pos = max(last_period, last_comma, last_question, last_exclamation)
        if cut_pos > 50:  # Si hay un punto o coma a más de 50 caracteres
            summary_text = summary_text[:cut_pos+1]
        print(f"✂️ Texto recortado de {original_word_count} a {len(summary_text.split())} palabras para ~60 segundos.")
    else:
        print(f"📝 Texto de {len(words)} palabras, duración estimada ~{len(words)//2} segundos.")

    # --- Comando para generar el audio con Edge TTS ---
    command = [
        "edge-tts",
        "--text", summary_text,
        "--voice", "es-CO-SalomeNeural",  # Voz de Colombia
        "--rate", "-5%",  # Reducir velocidad para mejorar claridad
        "--write-media", output_filename
    ]
    
    try:
        # Ejecutar el comando
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ Audio generado exitosamente: {output_filename}")
        
        # Verificar el tamaño del archivo
        if os.path.exists(output_filename):
            file_size = os.path.getsize(output_filename)
            print(f"   📊 Tamaño del archivo: {file_size / 1024:.2f} KB")
        
        return output_filename
        
    except FileNotFoundError:
        print("❌ Error: 'edge-tts' no está instalado. Instálalo con 'pip install edge-tts'")
        print("   También puedes probar: 'pip install edge-tts --upgrade'")
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al generar el audio: {e.stderr}")
        print("   Verifica que el texto no contenga caracteres especiales problemáticos.")
        return None
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def get_audio_duration_estimate(text):
    """
    Estima la duración del audio en segundos basado en el número de palabras.
    """
    words = text.split()
    word_count = len(words)
    # Estimación: 2.5 palabras por segundo en español
    estimated_seconds = int(word_count / 2.5)
    return estimated_seconds

# --- Función de prueba ---
if __name__ == '__main__':
    print("=== Probando audio_generator.py ===\n")
    
    # Texto de prueba (simula un resumen de 7 noticias)
    test_text = """
    Hoy en el mundo de la inteligencia artificial, OpenAI ha anunciado el lanzamiento de GPT-5, 
    su nuevo modelo con capacidad de contexto de 1 millón de tokens, superando significativamente 
    a la competencia. Por otro lado, la empresa china Kimi ha presentado su modelo K3, que promete 
    ser el modelo abierto de crecimiento más rápido en la historia. Microsoft, por su parte, ha 
    lanzado sus propios modelos de IA, compitiendo directamente con OpenAI y Anthropic, mientras 
    que Google ha anunciado Gemini Ultra para empresas, su modelo más avanzado. Además, Anthropic 
    ha publicado un documento oficial sobre su postura respecto a los modelos abiertos, generando 
    debate en la comunidad. En el ámbito regulatorio, la Unión Europea avanza en la ley de IA 
    que podría cambiar las reglas del juego. Finalmente, un estudio reciente muestra que la 
    adopción de IA en empresas ha crecido un 40% en el último año.
    """
    
    # Estimar duración
    estimated = get_audio_duration_estimate(test_text)
    print(f"📝 Texto de prueba: {len(test_text.split())} palabras")
    print(f"⏱️ Duración estimada: {estimated} segundos")
    
    # Generar audio
    audio_file = generate_audio(test_text, "test_audio.mp3")
    
    if audio_file:
        print(f"\n✅ Audio generado: {audio_file}")
        print("🎧 Puedes reproducirlo con cualquier reproductor de audio.")
    else:
        print("\n❌ Error al generar el audio de prueba.")