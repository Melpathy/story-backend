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
        
        payload = {
            "model": "mistral-medium",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a translator. Return translations in JSON format with a single key 'translation' containing the translated text."
                },
                {
                    "role": "user", 
                    "content": f"Translate the following to {target_language} and return ONLY a JSON object with the translation: '{text}'"
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            try:
                # Try to parse the response as JSON
                content = response_json["choices"][0]["message"]["content"].strip()
                translation_data = json.loads(content)
                
                # Extract just the translation from the JSON
                if isinstance(translation_data, dict) and "translation" in translation_data:
                    return translation_data["translation"]
                
            except json.JSONDecodeError:
                # If JSON parsing fails, try to clean up the response
                content = response_json["choices"][0]["message"]["content"].strip()
                # Remove any non-JSON text
                if '"translation"' in content:
                    try:
                        # Try to extract just the JSON part
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            translation_data = json.loads(json_str)
                            if "translation" in translation_data:
                                return translation_data["translation"]
                    except:
                        pass
                
        return text  # Fallback to original text

    except Exception as e:
        logging.error(f"Translation Error: {str(e)}")
        return text  # Return original text if translation fails
        

def get_language_config(language='english', custom_language=None):
    """Get language configuration based on selected language."""
    language = language.lower()
    
    # First check if it's one of our predefined languages
    if language in LANGUAGE_CONFIG:
        return LANGUAGE_CONFIG[language]
    
    # If not a predefined language, treat it as a custom language
    try:
        # Use Mistral to translate all necessary strings
        custom_config = {
            "story_title": translate_with_mistral("A Personalized Story for", language) + " {name}",
            "chapter_label": translate_with_mistral("Chapter", language),
            "illustration_label": translate_with_mistral("Illustration", language),
            "end_text": translate_with_mistral("The End", language),
            "by_author": translate_with_mistral("By", language) + " {author}",
            "no_illustrations": translate_with_mistral("(Illustrations not generated in this test.)", language),
            "loading_message": translate_with_mistral("Your story is being generated...", language),
            "error_message": translate_with_mistral("An error occurred while generating your story.", language),
            "success_message": translate_with_mistral("PDF successfully generated!", language),
            "processing_message": translate_with_mistral("Task is in progress.", language)
        }
        return custom_config
    except Exception as e:
        logging.error(f"Translation failed for language {language}: {str(e)}")
        return LANGUAGE_CONFIG['english']  # Fallback to English
    
    return LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG['english'])

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
