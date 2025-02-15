import logging
import requests
import os
import re
import json

# Language configuration dictionary
LANGUAGE_CONFIG = {
    "english": {
        "story_title": "A Personalized Story for {name}",
        "chapter_label": "Chapter",
        "illustration_label": "Illustration",
        "end_text": "The End",
        "by_author": "By {author}",
        "no_illustrations": "(Illustrations not generated in this test.)",
        "loading_message": "Your story is being generated...",
        "error_message": "An error occurred while generating your story.",
        "success_message": "PDF successfully generated!",
        "moral_label": "Moral",
        "processing_message": "Task is in progress."
    },
    "french": {
        "story_title": "Une Histoire Personnalisée pour {name}",
        "chapter_label": "Chapitre",
        "illustration_label": "Illustration",
        "end_text": "Fin",
        "by_author": "Par {author}",
        "no_illustrations": "(Illustrations non générées dans ce test.)",
        "loading_message": "Votre histoire est en cours de génération...",
        "error_message": "Une erreur s'est produite lors de la génération de votre histoire.",
        "success_message": "PDF généré avec succès !",
        "moral_label": "Morale",
        "processing_message": "La tâche est en cours."
    },
    "spanish": {
        "story_title": "Una Historia Personalizada para {name}",
        "chapter_label": "Capítulo",
        "illustration_label": "Ilustración",
        "end_text": "Fin",
        "by_author": "Por {author}",
        "no_illustrations": "(Ilustraciones no generadas en esta prueba.)",
        "loading_message": "Tu historia se está generando...",
        "error_message": "Ocurrió un error al generar tu historia.",
        "success_message": "¡PDF generado exitosamente!",
        "moral_label": "Moraleja",
        "processing_message": "La tarea está en progreso."
    },
    "german": {
        "story_title": "Eine persönliche Geschichte für {name}",
        "chapter_label": "Kapitel",
        "illustration_label": "Illustration",
        "end_text": "Ende",
        "by_author": "Von {author}",
        "no_illustrations": "(In diesem Test wurden keine Illustrationen generiert.)",
        "loading_message": "Deine Geschichte wird generiert...",
        "error_message": "Bei der Generierung deiner Geschichte ist ein Fehler aufgetreten.",
        "success_message": "PDF erfolgreich generiert!",
        "moral_label": "Moral",
        "processing_message": "Aufgabe wird bearbeitet."
    }
}

def translate_with_mistral(text, target_language):
    """Uses Mistral API to translate text with JSON output."""
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        # Enhanced prompt to enforce single language translation
        system_prompt = f"""You are a professional translator. You must ONLY translate to {target_language}.
        Never translate to any other language. Return ONLY a JSON object with the translation.
        Format: {{"translation": "your translated text"}}"""

        payload = {
            "model": "mistral-medium",
            "messages": [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": f"Translate ONLY to {target_language} and return ONLY a JSON object with the translation: '{text}'"
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            try:
                content = response_json["choices"][0]["message"]["content"].strip()
                translation_data = json.loads(content)
                
                if isinstance(translation_data, dict) and "translation" in translation_data:
                    return translation_data["translation"]
                
            except json.JSONDecodeError:
                content = response_json["choices"][0]["message"]["content"].strip()
                if '"translation"' in content:
                    try:
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            translation_data = json.loads(json_str)
                            if "translation" in translation_data:
                                return translation_data["translation"]
                    except:
                        pass
                
        return text

    except Exception as e:
        logging.error(f"Translation Error: {str(e)}")
        return text
        
def get_language_config(language='english', custom_language=None):
    """
    Get language configuration based on selected language.
    If it's a custom language, use that for translation.
    """
    # If custom_language is provided, use that instead of the standard language
    target_language = custom_language.lower() if custom_language else language.lower()
    
    # First check if it's one of our predefined languages
    if not custom_language and target_language in LANGUAGE_CONFIG:
        return LANGUAGE_CONFIG[target_language]
    
    # If we're here, we need to translate everything to the target language
    try:
        logging.info(f"Generating translations for language: {target_language}")
        
        # Define all strings that need translation
        strings_to_translate = {
            "story_title": "A Personalized Story for",  # {name} will be added later
            "chapter_label": "Chapter",
            "illustration_label": "Illustration",
            "end_text": "The End",
            "by_author": "By",  # {author} will be added later
            "no_illustrations": "(Illustrations not generated in this test.)",
            "loading_message": "Your story is being generated...",
            "error_message": "An error occurred while generating your story.",
            "success_message": "PDF successfully generated!",
            "moral_label": "Moral",
            "processing_message": "Task is in progress."
        }

        # Translate all strings
        custom_config = {}
        for key, text in strings_to_translate.items():
            # Always pass the target_language to translate_with_mistral
            translated_text = translate_with_mistral(text, target_language)
            
            # Handle placeholders for special cases
            if key == "story_title":
                custom_config[key] = f"{translated_text} " + "{name}"
            elif key == "by_author":
                custom_config[key] = f"{translated_text} " + "{author}"
            else:
                custom_config[key] = translated_text
            
            # Log for debugging
            logging.info(f"Translated {key} to {target_language}: {custom_config[key]}")

        return custom_config

    except Exception as e:
        logging.error(f"Translation failed for language {target_language}: {str(e)}")
        logging.warning(f"Falling back to English due to translation error")
        return LANGUAGE_CONFIG['english']

def format_language_strings(config, context):
    """Format language strings with provided context."""
    formatted_config = {}
    for key, value in config.items():
        try:
            formatted_config[key] = value.format(**context)
        except KeyError as e:
            logging.error(f"Missing context key for formatting: {str(e)}")
            formatted_config[key] = value
    return formatted_config
