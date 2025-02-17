import re
from typing import List, Dict, Optional
from config import API_CONFIG, IMAGE_CONFIG, STORY_LENGTH_CONFIG
from language_handler import translate_with_mistral
import logging
import requests

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
    
    def _call_mistral_api(self, prompt: str, max_tokens: int) -> Optional[Dict]:
        """Make API call to Mistral with proper error handling."""
        try:
            url = "https://api.mistral.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "mistral-medium",
                "messages": [
                    {"role": "system", "content": "You are an expert children's story writer."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Mistral API error: {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Error calling Mistral API: {str(e)}")
            return None
    
    def generate_story(self, prompt: str, chapter_label: str, story_length: str = "short") -> str:
        """Generate a structured story using Mistral API."""
        try:
            length_config = STORY_LENGTH_CONFIG.get(story_length, STORY_LENGTH_CONFIG["short"])
            max_tokens = length_config["max_tokens"]
            target_sections = length_config["target_sections"]
            
            formatted_prompt = f"""
            {prompt}
            Structure the story into approximately {target_sections} chapters.
            Ensure the story has a proper beginning, middle, and end.
            Each chapter should be balanced in length.
            IMPORTANT: Provide a complete story with proper resolution - do not end abruptly.
            Use "{chapter_label} X:" to label each chapter.
            """
            
            response = self._call_mistral_api(formatted_prompt, max_tokens)
            if response and "choices" in response and response["choices"]:
                story_text = response["choices"][0]["message"]["content"]
                return story_text
            return "Error generating story."
        except Exception as e:
            self.logger.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"
    
    def generate_bilingual_story(self, text: str, target_language: str, format_type: str) -> List[Dict]:
        """Generates and formats a bilingual story in the requested format."""
        self.logger.info(f"Generating bilingual story: format={format_type}, language={target_language}")
        
        primary_story = self.generate_story(text, "Chapter")
        secondary_story = translate_with_mistral(primary_story, target_language)
        
        if format_type.upper() == "AABB":
            sections = self.split_into_parallel_sections(
                primary_story,
                secondary_story,
                "Chapter",
                "Chapitre"
            )
            self.logger.info(f"Generated sections (AABB mode): {sections}")
            return sections
        else:
            primary_sentences = self.split_into_sentences(primary_story)
            secondary_sentences = self.split_into_sentences(secondary_story)
            sentence_pairs = [{"primary": primary_sentences[i], "secondary": secondary_sentences[i]} for i in range(min(len(primary_sentences), len(secondary_sentences)))]
            self.logger.info(f"Generated sentence pairs (ABAB mode): {sentence_pairs}")
            return [{"sentence_pairs": sentence_pairs}]
