from flask import Flask, request, jsonify, send_file
from weasyprint import HTML
from jinja2 import Template
import os
import tempfile  # Use temporary files instead of keeping data in memory
from io import BytesIO
import requests  # For calling external APIs
import replicate
import logging
import psutil
import gc  # For memory cleanup
from flask import Flask
from flask_cors import CORS
import re

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": ["https://mels-story-site.webflow.io"]}})

# Set up logging
logging.basicConfig(level=logging.INFO)

# ✅ Centralized API Keys (Easy to Switch APIs)
API_KEYS = {
    "mistral": os.getenv("MISTRAL_API_KEY"),
    "replicate": os.getenv("REPLICATE_API_TOKEN")
}

# Validate API Keys
if not API_KEYS["mistral"]:
    raise ValueError("Mistral API key not found. Set MISTRAL_API_KEY in environment variables.")

if not API_KEYS["replicate"]:
    raise ValueError("Replicate API key not found. Set REPLICATE_API_TOKEN in environment variables.")

# Initialize Replicate client
replicate_client = replicate.Client(api_token=API_KEYS["replicate"])


def log_memory_usage(stage):
    """Logs the current memory usage at different stages."""
    process = psutil.Process()
    mem_info = process.memory_info()
    logging.info(f"[{stage}] Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")  # Convert bytes to MB

def generate_image(prompt):
    """Generate an image using Replicate's Stable Diffusion 3 model."""
    
    # Uncomment the model you want to use
    # model_version = "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4"
    model_version = "stability-ai/stable-diffusion-3"  # Default model

    try:
        input_data = {
            "prompt": prompt,
            "width": 256,  # Lower resolution for memory optimization
            "height": 256
        }

        logging.info(f"📡 Calling Stable Diffusion with prompt: {prompt}")
        output = replicate_client.run(model_version, input=input_data)

        if not output or len(output) == 0:
            raise ValueError("❌ Replicate API did not return a valid image URL.")

        logging.info(f"✅ Generated Image URL: {output[0]}")
        return output[0]

    except Exception as e:
        logging.error(f"❌ Error generating image: {str(e)}")
        return None  # Return None instead of crashing

def generate_story_mistral(prompt, max_tokens=800):
    """Generate a story using Mistral API with structured sections."""
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEYS['mistral'].strip()}",
            "Content-Type": "application/json"
        }

        # Dynamically adjust tokens to avoid cutting off sections
        section_estimate = max(3, min(10, max_tokens // 150))  # Limits sections between 3-10
        prompt += f"""
        Structure the story into {section_estimate} sections.
        Clearly label each section as "SECTION X:". Ensure even distribution.
        """
        
        payload = {
            "model": "mistral-medium",
            "messages": [
                {"role": "system", "content": "You are an expert children's story writer. Generate a complete, structured story divided into sections. Each section should be clearly labeled."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9
        }

        logging.info("📡 Calling Mistral API for story generation...")
        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            return response_json["choices"][0]["message"]["content"]
        else:
            logging.error(f"❌ Mistral API Error: {response_json}")
            return f"Error generating story. API Response: {response_json}"

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Mistral API Request Error: {str(e)}")
        return f"Error generating story. Exception: {str(e)}"

    except Exception as e:
        logging.error(f"❌ Unknown Error in Mistral API: {str(e)}")
        return f"Error generating story. Exception: {str(e)}"


def split_story_into_sections(story_text):
    """Parses the generated story into structured sections."""
    sections = []
    # Improved regex: Handles variations like "Section 1:", "SECTION 1", or "section one"
    section_pattern = re.compile(r"(SECTION\s*\d+[:.]?)", re.IGNORECASE)
    parts = section_pattern.split(story_text)[1:]  

    for i in range(0, len(parts), 2):
        section_title = parts[i].strip().replace(":", "")
        section_content = parts[i + 1].strip() if i + 1 < len(parts) else ""

        # Generate a short summary for illustrations
        summary_prompt = f"Summarize this section in 2-3 sentences for an illustration: {section_content}"
        summary = generate_story_mistral(summary_prompt, max_tokens=50)

        sections.append({
            "title": section_title,
            "content": section_content,
            "summary": summary
        })

    return sections


def generate_image_per_section(sections):
    """Generates an image for each section's summary."""
    illustrations = []
    for section in sections:
        illustration_prompt = f"Children's storybook illustration for: {section['summary']}" if section['summary'] else "Illustrate this story section."
        image_url = generate_image(illustration_prompt)
        illustrations.append(image_url if image_url else "https://example.com/default_image.jpg")  # Fallback
    return illustrations



@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """Handles the story and PDF generation request."""
    try:
        # ✅ Get request data
        data = request.get_json()
        logging.info(f"Received Data: {data}")  # Debugging

        # ✅ Extract Fields (Using default values for missing fields)
        child_name = data.get('childName', 'child')
        age = data.get('age', 7)
        character_type = data.get('character-type', 'Boy')
        custom_character = data.get('custom-character', None)
        interests = data.get('interests', 'adventures')
        moral_lesson = data.get('moralLesson', 'kindness')
        toggle_customization = data.get('toggle-customization', 'no').strip().lower() == 'yes'
        story_genre = data.get('story-genre', 'Fantasy')
        story_tone = data.get('story-tone', 'Lighthearted')
        surprise_ending = str(data.get('surprise-ending', 'false')).strip().lower() == 'true'
        story_language = data.get('story-language', 'English')
        custom_language = data.get('custom-language', None)
        bilingual_mode = str(data.get('bilingual-mode', 'false')).strip().lower() == 'true'
        bilingual_language = data.get('bilingual-language', 'English')
        custom_bilingual_language = data.get('custom-bilingual-language', None)
        best_friend = data.get('best-friend', None)
        pet_name = data.get('pet-name', None)

        # ✅ Build the Story Prompt
        prompt = (
            f"Write a children's story for a {age}-year-old. "
            f"The main character is a {character_type.lower()} named {child_name}."
        )

        if custom_character:
            prompt += f" The character is specifically described as: {custom_character}."

        if interests:
            prompt += f" The story should include their interests: {interests}."

        prompt += f" The story should teach the moral lesson of {moral_lesson}."

        if toggle_customization:
            prompt += f" The genre is {story_genre} with a {story_tone} tone."

        if surprise_ending:
            prompt += " The story should include a surprise ending."

        if best_friend:
            prompt += f" The character's best friend, {best_friend}, is part of the adventure."

        if pet_name:
            prompt += f" Their pet, {pet_name}, plays an important role in the story."

        # ✅ Handle Bilingual Mode
        if bilingual_mode:
            if bilingual_language and bilingual_language.lower() == "other-bilingual" and custom_bilingual_language:
                prompt += f" The story should be written in both English and {custom_bilingual_language}."
            elif bilingual_language:
                prompt += f" The story should be written in both English and {bilingual_language}."


        # ✅ Handle Custom Story Language
        if story_language and story_language.lower() == "other-language" and custom_language:
            prompt += f" The story should be written in {custom_language}."

        log_memory_usage("Before Mistral API")
        
        # ✅ Log the prompt in the console
        logging.info(f"📝 Full AI Prompt:\n{prompt}\n")

        # ✅ Generate the Full Story
        full_story = generate_story_mistral(prompt, max_tokens=800)
        logging.info("Story generated successfully.")

        # ✅ Split into Sections
        sections = split_story_into_sections(full_story)
        logging.info(f"Story split into {len(sections)} sections.")

        # ✅ Generate Images for Each Section
        illustrations = generate_image_per_section(sections)

        log_memory_usage("After Mistral API")

        logging.info("Story generated successfully.")

        # ✅ Load and render HTML template
        with open("story_template.html") as template_file:
            template = Template(template_file.read())

         rendered_html = template.render(
            title=f"A Personalized Story for {child_name}",
            author=child_name,
            sections=sections,
            illustrations=illustrations
        )

        logging.info("Rendering PDF with WeasyPrint...")
        log_memory_usage("Before PDF Generation")

        # ✅ Generate PDF using a temporary file (reduces memory pressure)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            HTML(string=rendered_html).write_pdf(temp_pdf.name)
            pdf_filename = os.path.basename(temp_pdf.name)
            pdf_url = f"https://story-backend-g7he.onrender.com/download/{pdf_filename}"  # URL to access the PDF

        log_memory_usage("After PDF Generation")

        return jsonify({
            "status": "success",
            "message": "Story generated successfully!",
            "pdf_url": pdf_url
        })

    except MemoryError:
        logging.error("Memory limit exceeded! Consider reducing API responses or upgrading memory.")
        return jsonify({"status": "error", "message": "Server ran out of memory. Try reducing input size or upgrading the plan."}), 500

    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        gc.collect()
        log_memory_usage("After Request Cleanup")



# ✅ Add the new download route BELOW the generate-story function
@app.route('/download/<filename>')
def download_file(filename):
    """Serves the generated PDF for download."""
    pdf_path = f"/tmp/{filename}"  # Ensure this matches your PDF storage path
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=True)


# ✅ Ensure this runs at the bottom of your script (if applicable)
if __name__ == "__main__":
    app.run(debug=True)
