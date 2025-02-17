import re
from typing import List, Dict, Optional
from config import API_CONFIG, IMAGE_CONFIG, STORY_LENGTH_CONFIG
from language_handler import translate_with_mistral
import logging

class StoryGenerator:
    def __init__(self, mistral_api_key: str, replicate_client):
        self.mistral_api_key = mistral_api_key
        self.replicate_client = replicate_client
        self.logger = logging.getLogger(__name__)
    
    def split_into_sentences(self, text: str) -> List[str]:
        """Splits text into individual sentences, handling punctuation properly."""
        sentence_endings = re.compile(r'(?<=[.!?])\s+')
        return sentence_endings.split(text.strip())
    
    def _split_chapters(self, content: str, chapter_label: str) -> List[str]:
        """Split content into chapters while preserving order."""
        chapter_pattern = rf'(?i){chapter_label}\s*\d+\s*:?.*?\n'
        chapters = re.split(chapter_pattern, content)
        return [ch.strip() for ch in chapters if ch.strip()]
    
    def generate_story(self, prompt: str, chapter_label: str, story_length: str = "short") -> str:
        """
        Generate a story using the Mistral API with specified length and structure.
        
        Args:
            prompt (str): The story prompt including character and plot details
            chapter_label (str): Label to use for chapters (e.g., "Chapter", "Chapitre")
            story_length (str): Length specification ("short", "medium", "long")
        
        Returns:
            str: Generated story text with proper chapter structure
        """
        try:
            length_config = STORY_LENGTH_CONFIG.get(story_length, STORY_LENGTH_CONFIG["short"])
            max_tokens = length_config["max_tokens"]
            formatted_prompt = f"{prompt}\nEnsure the story has a structured beginning, middle, and end."
            response = translate_with_mistral(formatted_prompt, "english")
            if not response:
                self.logger.error("Failed to get a response from Mistral API")
                return "Error generating story."
            return response
        except Exception as e:
            self.logger.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"
    
    def translate_story(self, content: str, target_language: str, format_type: str) -> str:
        """
        Translate story content using Mistral API.
        Handles ABAB (sentence-based) and AABB (chapter-based) translation.
        """
        try:
            primary_chapters = self._split_chapters(content, "Chapter")
            translated_chapters = []
            
            if format_type.upper() == "ABAB":
                for chapter in primary_chapters:
                    sentences = self.split_into_sentences(chapter)
                    translated_sentences = [translate_with_mistral(sentence, target_language) for sentence in sentences]
                    translated_chapters.append(" ".join(translated_sentences))
            else:
                translated_chapters = [translate_with_mistral(chapter, target_language) for chapter in primary_chapters]
                
            return "\n\n".join(translated_chapters)
        except Exception as e:
            self.logger.error(f"Translation error: {str(e)}")
            return content
    
    def format_bilingual_story(self, primary_text: str, target_language: str, format_type: str) -> List[Dict]:
        """Formats the bilingual story according to the selected format (AABB or ABAB)."""
        if format_type.upper() == "AABB":
            return [{
                "content": primary_text,
                "content_second_language": self.translate_story(primary_text, target_language, format_type)
            }]
        else:  # ABAB
            primary_sentences = self.split_into_sentences(primary_text)
            secondary_sentences = self.split_into_sentences(self.translate_story(primary_text, target_language, format_type))
            return [{
                "sentence_pairs": [
                    {"primary": primary_sentences[i], "secondary": secondary_sentences[i]}
                    for i in range(min(len(primary_sentences), len(secondary_sentences)))
                ]
            }]
    
    def generate_bilingual_story(self, text: str, target_language: str, format_type: str) -> List[Dict]:
        """Generates and formats a bilingual story in the requested format."""
        return self.format_bilingual_story(text, target_language, format_type)
    
    def split_into_parallel_sections(self, primary_content: str, secondary_content: str, primary_label: str, secondary_label: str) -> List[Dict]:
        """Splits content into parallel sections (AABB format)."""
        return self._split_into_parallel_sections(primary_content, secondary_content, primary_label, secondary_label)
    
    def generate_illustration(self, prompt: str) -> str:
        """Generate an illustration using Replicate AI."""
        try:
            input_data = {
                "prompt": prompt,
                "width": IMAGE_CONFIG['WIDTH'],
                "height": IMAGE_CONFIG['HEIGHT']
            }
            output = self.replicate_client.run(IMAGE_CONFIG['MODEL'], input=input_data)
            return output[0] if output else ""
        except Exception as e:
            self.logger.error(f"Illustration generation error: {str(e)}")
            return ""
