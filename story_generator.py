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

            formatted_prompt = (
                f"{prompt}\n\n"
                f"Structure the story into about {target_sections} chapters. "
                f"Use \"{chapter_label} X:\" for each chapter. "
                "Provide a complete story with a proper resolution."
            )

            response = self._call_mistral_api(
                formatted_prompt, 
                max_tokens=max_tokens, 
                target_language=target_language
            )

            if response:
                    story_text = response["choices"][0]["message"]["content"]
                    # ...
                    return story_text
                else:
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

    def _ensure_story_completion(self, story_text, chapter_label, story_length="short"):
        """Attempt to generate a proper ending if needed."""
        completion_prompt = f"""
        Complete this story with a proper ending (1-2 paragraphs maximum):
        
        {story_text}
        """
        
        # Use the story_length parameter instead of max_tokens
        response = self._call_mistral_api(completion_prompt, max_tokens=200)
        if response:
            ending = response["choices"][0]["message"]["content"]
            return f"{story_text}\n\n{ending}"
        return story_text

    def _call_mistral_api(self, prompt, max_tokens=None, target_language="english"):
        """Make API call to Mistral and force output language."""
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
        # System instruction telling Mistral to output ONLY in the target language
        system_content = (
            f"You are an expert children's story writer. "
            f"All user instructions may be in English, but you MUST produce your final story text "
            f"ENTIRELY in {target_language}. "
            f"Do not respond in any other language."
        )
    
        payload = {
            "model": API_CONFIG['MISTRAL_MODEL'],
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens if max_tokens else API_CONFIG['MAX_TOKENS'],
            "temperature": 0.7
        }
    
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    def split_into_sections(self, story_text, chapter_label, story_length="short"):
        sections = []
        chapter_regex = re.compile(rf"({chapter_label}\s*\d+[:.]?)", re.IGNORECASE)
        parts = chapter_regex.split(story_text)[1:]
        
        # Parse ALL chapters that appear in the text
        # (Divide by 2 because split() returns [chapter_label, content, chapter_label, content, ...])
        section_count = len(parts) // 2
    
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
        # Change this to use story_length="short" instead of max_tokens
        return self.generate_story(summary_prompt, "Summary", story_length="short")

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
