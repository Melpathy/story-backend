import logging
import requests
from config import API_CONFIG, IMAGE_CONFIG, STORY_LENGTH_CONFIG
import re

class StoryGenerator:
    def __init__(self, api_key, replicate_client):
        self.api_key = api_key
        self.replicate_client = replicate_client

    def generate_story(self, prompt, chapter_label, story_length="short"):
        """Generate story using Mistral API with length consideration."""
        try:
            length_config = STORY_LENGTH_CONFIG[story_length]
            max_tokens = length_config["max_tokens"]
            target_sections = length_config["target_sections"]

            # Add length guidance to prompt
            formatted_prompt = f"""{prompt}
            Structure the story into approximately {target_sections} chapters.
            Ensure the story has a proper beginning, middle, and end.
            Each chapter should be balanced in length.
            IMPORTANT: Provide a complete story with proper resolution - do not end abruptly.
            Use "{chapter_label} X:" to label each chapter.
            """

            response = self._call_mistral_api(formatted_prompt, max_tokens)
            if response:
                story_text = response["choices"][0]["message"]["content"]
                if self._verify_story_completion(story_text):
                    return story_text
                else:
                    # If story seems incomplete, try to generate a proper ending
                    return self._ensure_story_completion(story_text, chapter_label, max_tokens)
            return "Error generating story."
        except Exception as e:
            logging.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"

    def _verify_story_completion(self, story_text):
        """Basic verification of story completion."""
        # Check for common ending indicators
        ending_indicators = [
            "The End",
            "Fin",
            "Ende",
            "concluded",
            "finally",
            "last",
            "happily ever after"
        ]
        
        # Check last few paragraphs for conclusion indicators
        last_paragraphs = story_text.split('\n')[-3:]
        text_to_check = ' '.join(last_paragraphs).lower()
        
        return any(indicator.lower() in text_to_check for indicator in ending_indicators)

    def _ensure_story_completion(self, story_text, chapter_label, max_tokens):
        """Attempt to generate a proper ending if needed."""
        completion_prompt = f"""
        Complete this story with a proper ending (1-2 paragraphs maximum):
        
        {story_text}
        """
        
        response = self._call_mistral_api(completion_prompt, max_tokens=200)
        if response:
            ending = response["choices"][0]["message"]["content"]
            return f"{story_text}\n\n{ending}"
        return story_text

    def _call_mistral_api(self, prompt, max_tokens=None):
        """Make API call to Mistral."""
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": API_CONFIG['MISTRAL_MODEL'],
            "messages": [
                {"role": "system", "content": "You are an expert children's story writer."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens if max_tokens is not None else API_CONFIG['MAX_TOKENS'],
            "temperature": 0.7
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json() if response.status_code == 200 else None

    def split_into_sections(self, story_text, chapter_label, story_length="short"):
        """Split story into sections."""
        sections = []
        chapter_regex = re.compile(rf"({chapter_label}\s*\d+[:.]?)", re.IGNORECASE)
        parts = chapter_regex.split(story_text)[1:]
        
        # Get target sections from config instead of using self.max_sections
        target_sections = STORY_LENGTH_CONFIG[story_length]["target_sections"]
        section_count = min(len(parts) // 2, target_sections)
        
        for i in range(0, section_count * 2, 2):
            section = self._process_section(parts[i:i+2], chapter_label)
            if section:
                sections.append(section)
        
        return sections

    def _process_section(self, part_pair, chapter_label):
        """Process a single story section."""
        if len(part_pair) < 2:
            return None
            
        chapter_number, content = part_pair
        content = content.strip()
        
        content_parts = content.split('\n', 1)
        title = ""
        main_content = content
        
        if len(content_parts) > 1:
            title = self._clean_title(content_parts[0], chapter_label)
            main_content = content_parts[1].strip()
            
        return {
            "chapter_number": chapter_number.strip().replace(":", ""),
            "title": title,
            "content": main_content,
            "summary": self._generate_summary(main_content)
        }

    def _clean_title(self, title, chapter_label):
        """Clean up chapter title."""
        title = re.sub(r'\*\*.*?\*\*', '', title).strip()
        return re.sub(rf'{chapter_label}\s*\d+\s*:?\s*', '', title, flags=re.IGNORECASE).strip()

    def _generate_summary(self, content):
        """Generate summary for illustrations."""
        summary_prompt = f"Summarize this section in 2-3 sentences for an illustration: {content}"
        return self.generate_story(summary_prompt, "Summary", max_tokens=50)

    def generate_illustration(self, prompt):
        """Generate illustration using Replicate."""
        try:
            input_data = {
                "prompt": prompt,
                "width": IMAGE_CONFIG['WIDTH'],
                "height": IMAGE_CONFIG['HEIGHT']
            }
            
            output = self.replicate_client.run(IMAGE_CONFIG['MODEL'], input=input_data)
            return output[0] if output else None
            
        except Exception as e:
            logging.error(f"Illustration generation error: {str(e)}")
            return None
