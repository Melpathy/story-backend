import logging
import requests
from config import API_CONFIG, IMAGE_CONFIG
import re

class StoryGenerator:
    def __init__(self, api_key, replicate_client):
        self.api_key = api_key
        self.replicate_client = replicate_client
        self.max_sections = API_CONFIG['STORY_SECTIONS']

    def generate_story(self, prompt, chapter_label, max_tokens=API_CONFIG['MAX_TOKENS']):
        """Generate story using Mistral API."""
        try:
            formatted_prompt = f"""{prompt}
            Structure the story into exactly {self.max_sections} chapters.
            Clearly label each chapter as "{chapter_label} X:". Ensure chapters are balanced in length.
            Each chapter should be well-defined and evenly distributed throughout the story."""

            response = self._call_mistral_api(formatted_prompt)
            if response:
                return response["choices"][0]["message"]["content"]
            return "Error generating story."
        except Exception as e:
            logging.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"

    def _call_mistral_api(self, prompt):
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
            "max_tokens": API_CONFIG['MAX_TOKENS'],
            "temperature": 0.7
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json() if response.status_code == 200 else None

    def split_into_sections(self, story_text, chapter_label):
        """Split story into sections."""
        sections = []
        chapter_regex = re.compile(rf"({chapter_label}\s*\d+[:.]?)", re.IGNORECASE)
        parts = chapter_regex.split(story_text)[1:]
        
        section_count = min(len(parts) // 2, self.max_sections)
        
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
