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
    
    def split_into_parallel_sections(self, primary_content: str, secondary_content: str, primary_label: str, secondary_label: str) -> List[Dict]:
        """Splits content into parallel sections for AABB format."""
        primary_chapters = self._split_chapters(primary_content, primary_label)
        secondary_chapters = self._split_chapters(secondary_content, secondary_label)
        
        combined_sections = []
        for i in range(min(len(primary_chapters), len(secondary_chapters))):
            section = {
                'chapter_number': f"{primary_label} {i+1}",
                'chapter_number_second_language': f"{secondary_label} {i+1}",
                'content': primary_chapters[i],
                'content_second_language': secondary_chapters[i]
            }
            combined_sections.append(section)
        
        return combined_sections
    
    def generate_story(self, prompt: str, chapter_label: str, story_length: str = "short") -> str:
        """
        Generate a story using the Mistral API with specified length and structure.
        """
        try:
            length_config = STORY_LENGTH_CONFIG.get(story_length, STORY_LENGTH_CONFIG["short"])
            max_tokens = length_config["max_tokens"]
            formatted_prompt = f"{prompt}\nEnsure the story has a structured beginning, middle, and end."
            response = translate_with_mistral(formatted_prompt, "english")
            self.logger.info(f"Generated story content: {response[:500]}...")
            if not response:
                self.logger.error("Failed to get a response from Mistral API")
                return "Error generating story."
            return response
        except Exception as e:
            self.logger.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"
    
    def generate_bilingual_story(self, text: str, target_language: str, format_type: str) -> List[Dict]:
        """Generates and formats a bilingual story in the requested format."""
        self.logger.info(f"Generating bilingual story: format={format_type}, language={target_language}")
        if format_type.upper() == "AABB":
            sections = self.split_into_parallel_sections(
                text,
                self.translate_story(text, target_language, format_type),
                "Chapter",
                "Chapitre"
            )
            self.logger.info(f"Generated sections (AABB mode): {sections}")
            return sections
        else:
            primary_sentences = self.split_into_sentences(text)
            secondary_sentences = self.split_into_sentences(self.translate_story(text, target_language, format_type))
            sentence_pairs = [{"primary": primary_sentences[i], "secondary": secondary_sentences[i]} for i in range(min(len(primary_sentences), len(secondary_sentences)))]
            self.logger.info(f"Generated sentence pairs (ABAB mode): {sentence_pairs}")
            return [{"sentence_pairs": sentence_pairs}]
    
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
