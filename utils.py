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
    """Build a richer, more original story prompt."""
    prompt_parts = [
        f"Write an engaging children's story for a {data.get('age', 7)}-year-old.",
        f"The main character is a {data.get('character-type', 'Boy').lower()} named {data.get('childName', 'child')}."
    ]

    if data.get('custom-character'):
        prompt_parts.append(f"The character is unique because: {data['custom-character']}.")

    if data.get('interests'):
        prompt_parts.append(f"The story should include themes about: {data['interests']}.")

    # Add unpredictability: Twist, conflict, or surprise element
    prompt_parts.append("Halfway through the story, introduce an unexpected event that changes everything!")
    prompt_parts.append("Make sure the story has an emotional moment that leaves the child feeling inspired.")

    # Encourage sensory details and immersive storytelling
    prompt_parts.append("Use vibrant descriptions, making the reader feel like they are inside the world of the story.")
    prompt_parts.append("Write in a way that keeps the child engaged, with suspense and excitement.")

    # Genre-based customization
    if data.get('toggle-customization') == 'yes':
        prompt_parts.append(f"The genre is {data.get('story-genre', 'Fantasy')}, with a {data.get('story-tone', 'Lighthearted')} tone.")

    if data.get('best-friend'):
        prompt_parts.append(f"Their best friend, {data['best-friend']}, joins the adventure.")
    if data.get('pet-name'):
        prompt_parts.append(f"Their pet, {data['pet-name']}, has a special ability in the story.")

    # Add optional bilingual storytelling
    if data.get('bilingual-mode') == 'true':
        second_language = data.get('custom-bilingual-language') or data.get('bilingual-language')
        if second_language and second_language.lower() != 'english':
            prompt_parts.append(f"The story should be told in both English and {second_language}.")

    return " ".join(prompt_parts)

