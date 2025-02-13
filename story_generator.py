from config import STORY_LENGTH_CONFIG, API_CONFIG, BASE_URLS
import requests

class StoryGenerator:
    def __init__(self, api_key, replicate_client):
        self.api_key = api_key
        self.replicate_client = replicate_client

    # Story Generation Methods
    def generate_story(self, prompt, chapter_label, story_length="short"):
        """Generate story using Mistral API with length consideration."""
        try:
            length_config = STORY_LENGTH_CONFIG[story_length]
            max_tokens = length_config["max_tokens"]
            target_sections = length_config["target_sections"]

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
                    return self._ensure_story_completion(story_text, chapter_label, max_tokens)
            return "Error generating story."
        except Exception as e:
            logging.error(f"Story generation error: {str(e)}")
            return f"Error generating story: {str(e)}"

    def _verify_story_completion(self, story_text):
        """Basic verification of story completion."""
        ending_indicators = [
            "The End", "Fin", "Ende", "concluded", "finally", "last",
            "happily ever after"
        ]
        
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

    # Translation Methods
    def translate_story(self, content, target_language, format_type):
        """Translate story content using Mistral API."""
        try:
            chunks = self._split_for_translation(content)
            translated_chunks = []
            max_retries = 3
            
            for chunk in chunks:
                for attempt in range(max_retries):
                    try:
                        translated_text = translate_with_mistral(chunk, target_language)
                        if self._validate_translation(translated_text, chunk):
                            translated_chunks.append(translated_text)
                            break
                        else:
                            logging.warning(f"Invalid translation on attempt {attempt + 1}")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        logging.warning(f"Translation attempt {attempt + 1} failed: {str(e)}")
            
            return self._reconstruct_story(translated_chunks, format_type)
            
        except Exception as e:
            logging.error(f"Translation error: {str(e)}")
            return content

    def _validate_translation(self, translated_text, original_text):
        """Validate translation quality."""
        if not translated_text or len(translated_text) < len(original_text) * 0.5:
            return False
        
        artifacts = ['[', ']', '{', '}', 'translate:', 'translation:']
        return not any(artifact in translated_text.lower() for artifact in artifacts)

    def _split_for_translation(self, content):
        """Split content into manageable chunks for translation."""
        chapter_splits = re.split(r'(Chapter \d+:?|Capitolo \d+:?|Chapitre \d+:?|Kapitel \d+:?)', content)
        
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

    def _reconstruct_story(self, chunks, format_type):
        """Reconstruct translated chunks into proper format."""
        if format_type == 'ABAB':
            return "\n\n".join(chunks)  # Simple joining for sentence pairs
        else:  # AABB format
            return "\n\n".join(chunks)  # Column format

    # Content Processing Methods
    def split_into_sections(self, story_text, chapter_label, story_length="short"):
        """Split story into sections."""
        sections = []
        chapter_regex = re.compile(rf"({chapter_label}\s*\d+[:.]?)", re.IGNORECASE)
        parts = chapter_regex.split(story_text)[1:]
        
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
        return self.generate_story(summary_prompt, "Summary", story_length="short")

    def _split_into_sentences(self, text):
        """Split text into sentences while preserving special characters."""
        text = text.replace('...', '[ELLIPSIS]')
        
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(]|$)', text)
        
        cleaned_sentences = []
        for sentence in sentences:
            if sentence.strip():
                restored = sentence.replace('[ELLIPSIS]', '...').strip()
                cleaned_sentences.append(restored)
        
        return cleaned_sentences

    # Format-Specific Methods
    def split_into_parallel_sections(self, primary_content, secondary_content, primary_label, secondary_label):
        """Split content for AABB (column) format."""
        primary_sections = self.split_into_sections(primary_content, primary_label)
        secondary_sections = self.split_into_sections(secondary_content, secondary_label)
        
        combined_sections = []
        for i in range(min(len(primary_sections), len(secondary_sections))):
            combined_sections.append({
                'chapter_number': primary_sections[i]['chapter_number'],
                'title': primary_sections[i]['title'],
                'title_second_language': secondary_sections[i]['title'],
                'content': primary_sections[i]['content'],
                'content_second_language': secondary_sections[i]['content'],
                'summary': primary_sections[i]['summary']
            })
        return combined_sections

    def split_into_sentence_pairs(self, primary_content, secondary_content):
        """Split content for ABAB (sentence) format."""
        primary_sections = self.split_into_sections(primary_content, "Chapter")
        secondary_sections = self.split_into_sections(secondary_content, "Chapter")
        
        combined_sections = []
        
        for p_section, s_section in zip(primary_sections, secondary_sections):
            primary_sentences = self._split_into_sentences(p_section['content'])
            secondary_sentences = self._split_into_sentences(s_section['content'])
            
            sentence_pairs = []
            max_sentences = min(len(primary_sentences), len(secondary_sentences))
            
            if len(primary_sentences) != len(secondary_sentences):
                logging.warning(
                    f"Sentence count mismatch: {len(primary_sentences)} primary vs "
                    f"{len(secondary_sentences)} secondary sentences"
                )
            
            for i in range(max_sentences):
                sentence_pairs.append({
                    'primary': primary_sentences[i],
                    'secondary': secondary_sentences[i]
                })
            
            chapter_section = {
                'chapter_number': p_section['chapter_number'],
                'title': p_section['title'],
                'title_second_language': s_section['title'],
                'sentence_pairs': sentence_pairs,
                'summary': p_section['summary']
            }
            
            combined_sections.append(chapter_section)
        
        return combined_sections

    # Illustration Methods
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
