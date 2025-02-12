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
    """
    Enhanced Mistral API translation with better handling of structural text.
    """
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        system_prompt = """You are a professional book translator specializing in story structural elements. 
        Your task is to translate keeping these guidelines:
        1. Maintain formal literary style appropriate for books
        2. Preserve any special characters or formatting
        3. Ensure translations are appropriate for story/chapter headings and UI elements
        4. Return only the direct translation without explanations
        Return translations in JSON format with a single key 'translation' containing the translated text."""

        payload = {
            "model": "mistral-medium",
            "messages": [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": f"Translate this book/story structural text to {target_language}. Return ONLY a JSON object with the translation: '{text}'"
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = requests.post(url, json=payload, headers=headers)
        if not response.ok:
            logging.error(f"Mistral API error: {response.status_code} - {response.text}")
            return text

        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            try:
                content = response_json["choices"][0]["message"]["content"].strip()
                content = content.replace("```json", "").replace("```", "").strip()
                translation_data = json.loads(content)
                
                if isinstance(translation_data, dict) and "translation" in translation_data:
                    translated_text = translation_data["translation"]
                    logging.info(f"Successfully translated '{text}' to '{translated_text}'")
                    return translated_text
                
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing error: {str(e)}")
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
                    except Exception as e:
                        logging.error(f"Failed to extract translation from partial JSON: {str(e)}")
                
        logging.warning(f"Falling back to original text due to translation failure")
        return text

    except Exception as e:
        logging.error(f"Translation error: {str(e)}")
        return text

def get_language_config(language='english', custom_language=None):
    """
    Get language configuration based on selected language.
    If language isn't predefined, use Mistral API to translate all necessary strings.
    """
    language = language.lower()
    
    # First check if it's one of our predefined languages
    if language in LANGUAGE_CONFIG:
        return LANGUAGE_CONFIG[language]
    
    # If not a predefined language, create a custom config using Mistral translations
    try:
        logging.info(f"Generating translations for non-predefined language: {language}")
        
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

        # Translate each string
        custom_config = {}
        for key, text in strings_to_translate.items():
            translated_text = translate_with_mistral(text, language)
            
            # Special handling for strings that need placeholders
            if key == "story_title":
                custom_config[key] = f"{translated_text} " + "{name}"
            elif key == "by_author":
                custom_config[key] = f"{translated_text} " + "{author}"
            else:
                custom_config[key] = translated_text

            logging.info(f"Translated {key}: {custom_config[key]}")

        return custom_config

    except Exception as e:
        logging.error(f"Translation failed for language {language}: {str(e)}")
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
