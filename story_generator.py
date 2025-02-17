import re
from typing import List, Dict
from config import API_CONFIG, IMAGE_CONFIG, STORY_LENGTH_CONFIG
from language_handler import translate_with_mistral

class StoryGenerator:
    def __init__(self, mistral_api_key: str, replicate_client):
        self.mistral_api_key = mistral_api_key
        self.replicate_client = replicate_client
    
    def split_into_sentences(self, text: str) -> List[str]:
        """Splits text into individual sentences, handling punctuation properly."""
        sentence_endings = re.compile(r'(?<=[.!?])\s+')
        return sentence_endings.split(text.strip())
    
    def translate_story(self, content: str, target_language: str, format_type: str) -> str:
        """
        Translate story content using Mistral API.
        For ABAB mode, the story is split into chapters and then into sentences,
        translating each sentence individually. For AABB mode, each chapter is translated in one go.
        
        Args:
            content (str): Original story content
            target_language (str): Target language for translation
            format_type (str): Format type ('AABB' for side-by-side or 'ABAB' for alternating sentences)
            
        Returns:
            str: Translated story content
        """
        try:
            if format_type.upper() == "ABAB":
                # Sentence-by-sentence translation for alternating format
                primary_chapters = self._split_chapters(content, "Chapter")
                translated_chapters = []
                for chapter in primary_chapters:
                    sentences = self.split_into_sentences(chapter)
                    translated_sentences = [translate_with_mistral(sentence, target_language) for sentence in sentences]
                    translated_chapters.append(" ".join(translated_sentences))
                return "\n\n".join(translated_chapters)
            else:
                # Chapter-based translation for parallel (AABB) format
                primary_chapters = self._split_chapters(content, "Chapter")
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
            secondary_sentences = self.translate_story(primary_text, target_language, format_type).split(" ")
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
        """
        Public method to split content into parallel sections (AABB format).
        This wraps the internal _split_into_parallel_sections method.
        """
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
