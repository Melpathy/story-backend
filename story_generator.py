from typing import List, Dict, Optional, Union
import logging
import requests
from config import API_CONFIG, IMAGE_CONFIG, STORY_LENGTH_CONFIG
import re
from language_handler import translate_with_mistral

class StoryGenerator:
    """
    A professional story generation and translation system.
    
    This class handles story generation, translation, and formatting for a bilingual
    children's story system. It supports multiple story lengths, translation formats,
    and chapter organization methods.
    """

    def __init__(self, api_key: str, replicate_client):
        """
        Initialize the StoryGenerator with required API credentials.

        Args:
            api_key (str): Mistral API key for story generation and translation
            replicate_client: Replicate client instance for illustration generation
        """
        self.api_key = api_key
        self.replicate_client = replicate_client
        self.logger = logging.getLogger(__name__)

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
            target_sections = length_config["target_sections"]

            formatted_prompt = self._format_story_prompt(prompt, chapter_label, target_sections)
            response = self._call_mistral_api(formatted_prompt, max_tokens)

            if not response or 'choices' not in response:
                self.logger.error("Failed to get valid response from Mistral API")
                return "Error generating story."

            story_text = response["choices"][0]["message"]["content"]
            return self._ensure_story_completion(story_text, chapter_label, max_tokens)

        except Exception as e:
            self.logger.error(f"Story generation error: {str(e)}", exc_info=True)
            return f"Error generating story: {str(e)}"

    def translate_story(self, content: str, target_language: str, format_type: str) -> str:
        try:
            # Get chapter label from language config
            chapter_label = self.get_language_chapter_label(target_language)
            
            # Replace chapter marker before translation
            content = content.replace("Chapter", chapter_label)
            
            # Preserve other special tokens
            preserved_content = self._preserve_special_tokens(content)
            
            # Translate and restore
            translated = translate_with_mistral(preserved_content, target_language)
            return self._restore_chapter_labels(translated, target_language)
            
        except Exception as e:
            self.logger.error(f"Translation error: {str(e)}")
            return content

    def split_into_parallel_sections(
        self, 
        primary_content: str, 
        secondary_content: str, 
        primary_label: str, 
        secondary_label: str
    ) -> List[Dict]:
        """
        Split content into parallel sections for side-by-side display (AABB format).

        Args:
            primary_content (str): Original language content
            secondary_content (str): Translated content
            primary_label (str): Chapter label in primary language
            secondary_label (str): Chapter label in secondary language

        Returns:
            List[Dict]: List of chapter sections with paired content
        """
        try:
            primary_chapters = self._split_chapters(primary_content, primary_label)
            secondary_chapters = self._split_chapters(secondary_content, secondary_label)

            self._validate_chapter_counts(primary_chapters, secondary_chapters)
            return self._combine_parallel_sections(
                primary_chapters, 
                secondary_chapters, 
                primary_label, 
                secondary_label
            )

        except Exception as e:
            self.logger.error(f"Error in parallel section splitting: {str(e)}", exc_info=True)
            return []

    def split_into_sentence_pairs(
        self, 
        primary_content: str, 
        secondary_content: str
    ) -> List[Dict]:
        """
        Split content into alternating sentence pairs (ABAB format).

        Args:
            primary_content (str): Original language content
            secondary_content (str): Translated content

        Returns:
            List[Dict]: List of chapters with sentence pairs
        """
        try:
            primary_chapters = self._split_chapters(primary_content, "Chapter")
            secondary_chapters = self._split_chapters(secondary_content, "Chapitre")

            return self._create_sentence_paired_sections(primary_chapters, secondary_chapters)

        except Exception as e:
            self.logger.error(f"Error in sentence pair splitting: {str(e)}", exc_info=True)
            return []

    def generate_illustration(self, prompt: str) -> Optional[str]:
        """
        Generate illustration using Replicate API.

        Args:
            prompt (str): Description of the illustration to generate

        Returns:
            Optional[str]: URL of generated illustration or None if generation fails
        """
        try:
            input_data = {
                "prompt": prompt,
                "width": IMAGE_CONFIG['WIDTH'],
                "height": IMAGE_CONFIG['HEIGHT']
            }
            
            output = self.replicate_client.run(IMAGE_CONFIG['MODEL'], input=input_data)
            return output[0] if output else None

        except Exception as e:
            self.logger.error(f"Illustration generation error: {str(e)}", exc_info=True)
            return None

    # Private Helper Methods

    def _format_story_prompt(self, prompt: str, chapter_label: str, target_sections: int) -> str:
        """Format the story generation prompt with structural requirements."""
        return f"""{prompt}
        Structure the story into approximately {target_sections} chapters.
        Ensure the story has a proper beginning, middle, and end.
        Each chapter should be balanced in length.
        IMPORTANT: Provide a complete story with proper resolution - do not end abruptly.
        Use "{chapter_label} X:" to label each chapter.
        """

    def _call_mistral_api(self, prompt: str, max_tokens: Optional[int] = None) -> Optional[Dict]:
        """Make API call to Mistral with error handling."""
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
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Mistral API call failed: {str(e)}", exc_info=True)
            return None

    def _preserve_special_tokens(self, content: str) -> str:
        """Preserve special tokens and formatting during translation."""
        replacements = {
            "Chapter": "###CHAPTER###",
            "...": "###ELLIPSIS###",
            "Mr.": "###MR###",
            "Mrs.": "###MRS###",
            "Dr.": "###DR###"
        }
        
        for original, token in replacements.items():
            content = content.replace(original, token)
        return content

    def _restore_chapter_labels(self, content: str, target_language: str) -> str:
        """Restore special tokens while maintaining consistent formatting."""
        # Restore only special characters and formatting
        replacements = {
            "###ELLIPSIS###": "...",
            "###MR###": "Mr.",
            "###MRS###": "Mrs.",
            "###DR###": "Dr."
        }
        
        for token, original in replacements.items():
            content = content.replace(token, original)
        
        return content

    def _split_chapters(self, content: str, chapter_label: str) -> List[str]:
        """Split content into chapters with proper handling of formatting."""
        chapter_pattern = rf'(?i){chapter_label}\s*\d+\s*:?'
        chapters = re.split(chapter_pattern, content)
        return [ch.strip() for ch in chapters if ch.strip()]

    def _validate_chapter_counts(self, primary_chapters: List[str], secondary_chapters: List[str]):
        """Validate chapter counts match between translations."""
        if len(primary_chapters) != len(secondary_chapters):
            self.logger.warning(
                f"Chapter count mismatch: {len(primary_chapters)} vs {len(secondary_chapters)}"
            )

    def _combine_parallel_sections(
        self, 
        primary_chapters: List[str],
        secondary_chapters: List[str],
        primary_label: str,
        secondary_label: str
    ) -> List[Dict]:
        """Combine chapters into parallel sections for AABB format."""
        combined_sections = []
        
        for i in range(min(len(primary_chapters), len(secondary_chapters))):
            primary_parts = self._extract_chapter_parts(primary_chapters[i])
            secondary_parts = self._extract_chapter_parts(secondary_chapters[i])
            
            section = {
                'chapter_number': f"{primary_label} {i+1}",
                'chapter_number_second_language': f"{secondary_label} {i+1}",
                'title': primary_parts['title'],
                'title_second_language': secondary_parts['title'],
                'content': primary_parts['content'],
                'content_second_language': secondary_parts['content'],
                'summary': self._generate_summary(primary_parts['content'])
            }
            combined_sections.append(section)
            
        return combined_sections

    def _create_sentence_paired_sections(
        self,
        primary_chapters: List[str],
        secondary_chapters: List[str]
    ) -> List[Dict]:
        """Create sentence-paired sections for ABAB format."""
        combined_sections = []
        
        for i in range(min(len(primary_chapters), len(secondary_chapters))):
            primary_parts = self._extract_chapter_parts(primary_chapters[i])
            secondary_parts = self._extract_chapter_parts(secondary_chapters[i])
            
            primary_sentences = self._split_into_sentences(primary_parts['content'])
            secondary_sentences = self._split_into_sentences(secondary_parts['content'])
            
            sentence_pairs = self._create_sentence_pairs(primary_sentences, secondary_sentences)
            
            section = {
                'chapter_number': f"Chapter {i+1}",
                'title': primary_parts['title'],
                'title_second_language': secondary_parts['title'],
                'sentence_pairs': sentence_pairs,
                'summary': self._generate_summary(primary_parts['content'])
            }
            combined_sections.append(section)
            
        return combined_sections

    def _create_sentence_pairs(
        self,
        primary_sentences: List[str],
        secondary_sentences: List[str]
    ) -> List[Dict]:
        """Create paired sentences for ABAB format."""
        pairs = []
        max_sentences = max(len(primary_sentences), len(secondary_sentences))
        
        for i in range(max_sentences):
            pair = {
                'primary': primary_sentences[i] if i < len(primary_sentences) else "",
                'secondary': secondary_sentences[i] if i < len(secondary_sentences) else ""
            }
            pairs.append(pair)
            
        return pairs

    def _extract_chapter_parts(self, chapter_text: str) -> Dict[str, str]:
        """Extract title and content from chapter text."""
        parts = chapter_text.split('\n', 1)
        if len(parts) > 1:
            return {
                'title': parts[0].strip(),
                'content': parts[1].strip()
            }
        return {
            'title': '',
            'content': parts[0].strip()
        }

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences with proper handling of special cases."""
        if not text:
            return []
            
        # Temporarily replace special cases
        preserved_text = self._preserve_special_tokens(text)
        
        # Split on sentence endings while preserving quotations
        pattern = r'(?<=[.!?])\s+(?=[A-Z]|"[A-Z])'
        sentences = re.split(pattern, preserved_text)
        
        # Restore special cases and clean
        return [
            self._restore_chapter_labels(sentence.strip(), "english")
            for sentence in sentences
            if sentence.strip()
        ]

    def _generate_summary(self, content: str) -> str:
        """Generate a summary for illustration purposes."""
        summary_prompt = f"Summarize this section in 2-3 sentences for an illustration: {content}"
        return self.generate_story(summary_prompt, "Summary", "short")

    def _verify_story_completion(self, story_text: str) -> bool:
        """Verify story has proper ending indicators."""
        ending_indicators = [
            "The End", "Fin", "Ende", "concluded", "finally", "last",
            "happily ever after"
        ]
        
        last_paragraphs = story_text.split('\n')[-3:]
        text_to_check = ' '.join(last_paragraphs).lower()
        
        return any(indicator.lower() in text_to_check for indicator in ending_indicators)

    def _ensure_story_completion(self, story_text: str, chapter_label: str, max_tokens: int) -> str:
        """Ensure story has proper completion and ending."""
        if self._verify_story_completion(story_text):
            return story_text
            
        completion_prompt = f"""
        Complete this story with a proper ending (1-2 paragraphs maximum):
        
        {story_text}
        """
        
        response = self._call_mistral_api(completion_prompt, max_tokens=200)
        if response and 'choices' in response:
            ending = response["choices"][0]["message"]["content"]
            return f"{story_text}\n\n{ending}"
            
        return story_text

    def _split_for_translation(self, content: str) -> List[str]:
        """
        Split content into manageable chunks for translation.
        
        Args:
            content (str): Story content to be split
            
        Returns:
            List[str]: List of content chunks ready for translation
        """
        # Split on chapter markers
        chapter_pattern = r'(###CHAPTER###\s*\d+:?)'
        chapter_splits = re.split(chapter_pattern, content)
        
        chunks = []
        current_chunk = ""
        
        for i in range(0, len(chapter_splits)):
            if i % 2 == 0:  # Content
                if chapter_splits[i].strip():
                    chunks.append(current_chunk + chapter_splits[i])
                    current_chunk = ""
            else:  # Chapter header
                current_chunk = chapter_splits[i] + "\n"
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _reconstruct_story(self, chunks: List[str], format_type: str) -> str:
        """
        Reconstruct translated chunks into proper story format.
        
        Args:
            chunks (List[str]): Translated story chunks
            format_type (str): Format specification ('AABB' or 'ABAB')
            
        Returns:
            str: Reconstructed story with proper formatting
        """
        if not chunks:
            return ""
            
        if format_type == 'ABAB':
            # For sentence-by-sentence alternation, maintain spacing
            return "\n\n".join(
                chunk.strip()
                for chunk in chunks
                if chunk.strip()
            )
        else:
            # For side-by-side format, maintain chapter structure
            reconstructed = []
            for chunk in chunks:
                cleaned_chunk = chunk.strip()
                if cleaned_chunk:
                    # Add proper spacing around chapter headers
                    if re.match(r'^(Chapter|Chapitre|Capítulo|Kapitel)\s*\d+:', cleaned_chunk):
                        reconstructed.append(f"\n{cleaned_chunk}\n")
                    else:
                        reconstructed.append(cleaned_chunk)
                        
            return "\n".join(reconstructed)

    def generate_parallel_story(
        self, 
        prompt: str, 
        primary_label: str,
        secondary_label: str,
        target_language: str,
        format_type: str = 'AABB',
        story_length: str = 'short'
    ) -> Dict:
        """
        Generate a complete bilingual story with all necessary components.
        
        Args:
            prompt (str): Story generation prompt
            primary_label (str): Chapter label in primary language
            secondary_label (str): Chapter label in secondary language
            target_language (str): Target language for translation
            format_type (str): Format specification ('AABB' or 'ABAB')
            story_length (str): Story length specification
            
        Returns:
            Dict: Complete story package with both languages and all sections
        """
        try:
            # Generate primary story
            primary_story = self.generate_story(prompt, primary_label, story_length)
            if "Error generating story" in primary_story:
                raise ValueError("Failed to generate primary story")

            # Translate to secondary language
            secondary_story = self.translate_story(
                primary_story,
                target_language,
                format_type
            )

            # Split into appropriate format
            if format_type == 'AABB':
                sections = self.split_into_parallel_sections(
                    primary_story,
                    secondary_story,
                    primary_label,
                    secondary_label
                )
            else:
                sections = self.split_into_sentence_pairs(
                    primary_story,
                    secondary_story
                )

            # Generate illustrations if configured
            illustrations = None
            if IMAGE_CONFIG.get('ENABLED', False):
                illustrations = []
                for section in sections:
                    if section.get('summary'):
                        illustration = self.generate_illustration(section['summary'])
                        illustrations.append({
                            'url': illustration,
                            'caption': section['summary']
                        } if illustration else None)

            return {
                'sections': sections,
                'illustrations': illustrations,
                'format_type': format_type,
                'primary_language': 'english',
                'secondary_language': target_language
            }

        except Exception as e:
            self.logger.error(f"Error generating parallel story: {str(e)}", exc_info=True)
            return {
                'error': f"Failed to generate story: {str(e)}",
                'sections': [],
                'illustrations': None
            }
