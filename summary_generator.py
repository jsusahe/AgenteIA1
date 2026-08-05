# summary_generator.py (fragmento de generate_summary_fallback)

def generate_summary_fallback(selected_news):
    """Genera un resumen básico usando la información real de las noticias cuando DeepSeek falla."""
    print("🔄 Usando modo de respaldo: generando resumen básico...")
    
    summary_text = "Resumen del día (generado automáticamente por el agente):\n\n"
    news_list = []
    
    for i, item in enumerate(selected_news[:7]):
        titulo = item.get('title', 'Sin título')
        fuente = item.get('fuente', 'Fuente desconocida')
        resumen = item.get('resumen', '')
        url = item.get('url', '#')
        tipo = item.get('tipo', 'externo')
        
        # Asegurar que el resumen tenga al menos 3 renglones
        if len(resumen) < 150 and resumen:
            resumen = resumen + " Este tema es relevante para el sector tecnológico y la innovación en inteligencia artificial."
        elif not resumen:
            resumen = "Noticia destacada del día sobre inteligencia artificial."
        
        summary_text += f"{i+1}. {titulo}\n   Fuente: {fuente}\n   {resumen[:200]}...\n\n"
        
        news_list.append({
            'title': titulo,
            'resumen': resumen[:300],
            'fuente': fuente,
            'tipo': tipo,
            'url': url
        })
    
    return {
        "summary": summary_text,
        "news": news_list
    }