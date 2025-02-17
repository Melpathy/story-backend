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
    
    def _verify_story_completion(self, story_text: str) -> bool:
        """Checks if the story has a proper ending."""
        ending_indicators = ["The End", "Fin", "Ende", "concluded", "finally", "last", "happily ever after"]
        last_paragraphs = story_text.split('\n')[-3:]
        text_to_check = ' '.join(last_paragraphs).lower()
        return any(indicator.lower() in text_to_check for indicator in ending_indicators)
    
    def _ensure_story_completion(self, story_text: str, chapter_label: str, max_tokens: int) -> str:
        """Attempts to generate a proper ending if needed."""
        completion_prompt = f"""
        Complete this story with a proper ending (1-2 paragraphs maximum):
        
        {story_text}
        """
        response = self._call_mistral_api(completion_prompt, max_tokens=200)
        if response and "choices" in response and response["choices"]:
            ending = response["choices"][0]["message"]["content"]
            return f"{story_text}\n\n{ending}"
        return story_text
    
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
                if self._verify_story_completion(story_text):
                    return story_text
                else:
                    return self._ensure_story_completion(story_text, chapter_label, max_tokens)
            return "Error generating story."
        except Exception as e:
            self.logger.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"
