import os
import logging
import psutil
from datetime import datetime

def sanitize_filename(filename):
    """Sanitize filename for safe storage."""
    return filename.strip().replace(' ', '_')

def get_s3_key(filename):
    """Generate S3 key with date prefix."""
    date_prefix = datetime.utcnow().strftime('%Y-%m-%d')
    return f"pdfs/{date_prefix}/{sanitize_filename(filename)}"

def log_memory_usage(stage):
    """Log memory usage at different stages."""
    process = psutil.Process()
    mem_info = process.memory_info()
    logging.info(f"[{stage}] Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")

def build_story_prompt(data, formatted_lang):
    """Build story prompt from request data."""
    prompt_parts = [
        f"Write a children's story for a {data.get('age', 7)}-year-old.",
        f"The main character is a {data.get('character-type', 'Boy').lower()} named {data.get('childName', 'child')}."
    ]

    if data.get('custom-character'):
        prompt_parts.append(f"The character is specifically described as: {data['custom-character']}.")

    if data.get('interests'):
        prompt_parts.append(f"The story should include their interests: {data['interests']}.")

    # Add moral lessons
    moral_lessons = data.get('moralLesson', [])
    if isinstance(moral_lessons, str):
        moral_lessons = [moral_lessons]
    if moral_lessons:
        prompt_parts.append(f"The story should teach the moral lessons of {', '.join(moral_lessons)}.")

    # Add customization
    if data.get('toggle-customization') == 'yes':
        prompt_parts.append(f"The genre is {data.get('story-genre', 'Fantasy')} with a {data.get('story-tone', 'Lighthearted')} tone.")

    # Add characters
    if data.get('best-friend'):
        prompt_parts.append(f"The character's best friend, {data['best-friend']}, is part of the adventure.")
    if data.get('pet-name'):
        prompt_parts.append(f"Their pet, {data['pet-name']}, plays an important role in the story.")

    # Add language settings
    if data.get('bilingual-mode') == 'true':
        second_language = data.get('custom-bilingual-language') or data.get('bilingual-language')
        if second_language and second_language.lower() != 'english':
            prompt_parts.append(f"The story should be written in both English and {second_language}.")
    elif data.get('story-language', '').lower() != 'english':
        language = data.get('custom-language') or data.get('story-language')
        prompt_parts.append(f"The story should be written in {language}.")

    return " ".join(prompt_parts)
