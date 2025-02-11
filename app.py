from celery import Celery
from flask import Flask, request, jsonify, send_file
from weasyprint import HTML
from jinja2 import Template
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import time
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
app.config['CELERY_BROKER_URL'] = 'redis://red-cuki0556l47c73cc9vi0:6379/0'  # ✅ Use Redis as Celery Broker
app.config['CELERY_RESULT_BACKEND'] = 'redis://red-cuki0556l47c73cc9vi0:6379/0'  # ✅ Store results in Redis
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_RESULT_BACKEND'])
celery.conf.broker_connection_retry_on_startup = True  # ✅ New setting to avoid warnings


app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # ✅ Allow up to 16MB requests

# ✅ Ensure CORS allows Webflow requests
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize S3 Client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)

def generate_presigned_url(bucket_name, s3_key, expiration=86400):
    """
    Generate a temporary pre-signed URL for accessing private PDFs on S3.
    """
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiration  # Link valid for 24 hours
        )
        return presigned_url
    except NoCredentialsError:
        return "Error: AWS credentials not found."
        
@app.after_request
def add_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Set up logging
logging.basicConfig(level=logging.INFO)

# ✅ Centralized API Keys (Easy to Switch APIs)
API_KEYS = {
    "mistral": os.getenv("MISTRAL_API_KEY"),
    "replicate": os.getenv("REPLICATE_API_TOKEN")
}


@celery.task
def generate_pdf_task(html_content, pdf_filename):
    """
    Generate PDF, upload to S3, and return a temporary pre-signed URL.
    """

    # ✅ Save the PDF in a temporary directory
    pdf_dir = "/tmp"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_filename.strip().replace(' ', '_'))

    logging.info(f"📂 Generating PDF at: {pdf_path}")

    try:
        # ✅ Generate PDF
        HTML(string=html_content).write_pdf(pdf_path)
        logging.info(f"✅ PDF successfully saved: {pdf_path}")

        # ✅ Debugging: Check if bucket name exists
        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("❌ ERROR: S3_BUCKET_NAME environment variable is missing!")

        # ✅ Store PDFs with timestamps
        date_prefix = datetime.utcnow().strftime('%Y-%m-%d')  # Example: "2025-02-10"
        s3_key = f"pdfs/{date_prefix}/{pdf_filename.strip().replace(' ', '_')}"

        logging.info(f"📡 Uploading PDF to S3 bucket: {bucket_name}, Key: {s3_key}")

        # ✅ Upload to S3
        s3_client.upload_file(pdf_path, bucket_name, s3_key, ExtraArgs={'ContentType': 'application/pdf'})

        # ✅ Generate Pre-Signed URL
        presigned_url = generate_presigned_url(bucket_name, s3_key, expiration=86400)  # 24 hours
        logging.info(f"✅ Pre-signed URL generated: {presigned_url}")

        return presigned_url  # ✅ Return the temporary URL instead of a permanent S3 link

    except Exception as e:
        logging.error(f"❌ PDF Generation Failed: {str(e)}")
        return None

        

@app.route('/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Check Celery task status and return S3 URL if ready."""
    task = generate_pdf_task.AsyncResult(task_id)

    if task.state == "PENDING":
        return jsonify({"status": "pending", "message": "PDF is still being generated."})

    elif task.state == "SUCCESS":
        s3_url = task.result  # ✅ Get S3 URL
        if s3_url:
            return jsonify({
                "status": "completed",
                "pdf_url": s3_url,
                "message": f"PDF successfully generated! Download here: {s3_url}"
            })
        else:
            return jsonify({"status": "error", "message": "Task completed but no PDF URL found."}), 500

    elif task.state == "FAILURE":
        return jsonify({"status": "failed", "message": "Task failed. Please try again."}), 500

    return jsonify({"status": task.state, "message": "Task is in progress."})


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

def translate_with_mistral(text, target_language):
    """ Uses Mistral API to translate text if not predefined. """
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEYS['mistral'].strip()}",
            "Content-Type": "application/json"
        }
        
        mistral_prompt = f"Translate '{text}' into {target_language}. Only return the translated word."
        
        payload = {
            "model": "mistral-medium",
            "messages": [
                {"role": "system", "content": "You are a translator."},
                {"role": "user", "content": mistral_prompt}
            ],
            "max_tokens": 10,
            "temperature": 0.3
        }

        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            return response_json["choices"][0]["message"]["content"].strip().capitalize()
        else:
            logging.error(f"❌ Translation Error: {response_json}")
            return "Chapter"  # Fallback to English

    except Exception as e:
        logging.error(f"❌ Translation Error: {str(e)}")
        return "Chapter"  # Fallback to English

def generate_story_mistral(prompt, chapter_label, max_tokens=800):
    """Generate a story using Mistral API with structured sections."""
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEYS['mistral'].strip()}",
            "Content-Type": "application/json"
        }

        # Dynamically adjust tokens to control section size
        max_sections = 3  # Limit to 3 sections
        
        # Add chapter formatting instructions to prompt
        formatted_prompt = f"""{prompt}
        Structure the story into exactly {max_sections} chapters.
        Clearly label each chapter as "{chapter_label} X:". Ensure chapters are balanced in length.
        Each chapter should be well-defined and evenly distributed throughout the story.
        """
        
        payload = {
            "model": "mistral-medium",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are an expert children's story writer. Generate a complete, structured story divided into sections. Each section should be clearly labeled."
                },
                {
                    "role": "user", 
                    "content": formatted_prompt
                }
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


def split_story_into_sections(story_text, chapter_label, max_sections=3):
    """ Parses the story into structured sections, ensuring no more than max_sections. """
    sections = []
    
    # Dynamically detect "Chapter X" in the correct language
    chapter_regex = re.compile(rf"({chapter_label}\s*\d+[:.]?)", re.IGNORECASE)
    parts = chapter_regex.split(story_text)[1:]  # Splits the story at each "Chapter X:"

    # Ensure we don't exceed the max section count
    section_count = min(len(parts) // 2, max_sections)

    for i in range(0, section_count * 2, 2):  
        chapter_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        
        # Extract the chapter title from the first line of content
        content_lines = chapter_content.split('\n', 1)
        if len(content_lines) > 1:
            chapter_title = content_lines[0].strip()
            main_content = content_lines[1].strip()
        else:
            chapter_title = ""
            main_content = chapter_content

        # Generate a short summary for illustrations
        summary_prompt = f"Summarize this section in 2-3 sentences for an illustration: {main_content}"
        summary = generate_story_mistral(summary_prompt, chapter_label, max_tokens=50)

        sections.append({
            "chapter_number": parts[i].strip().replace(":", ""),
            "title": chapter_title,
            "content": main_content,
            "summary": summary
        })

    return sections



def generate_image_per_section(sections, story_language='english'):
    """Generates an image and a caption in the correct language for each section."""
    illustrations = []
    
    for section in sections:
        # Generate illustration based on section summary
        illustration_prompt = f"Children's storybook illustration for: {section['summary']}"
        image_url = generate_image(illustration_prompt)

        # Generate a brief caption in the correct language
        caption_prompt = f"""Write a single brief caption (maximum 8 words) in {story_language} for this illustration: {section['summary']}.
        ONLY return the caption text, nothing else."""
        
        caption = generate_story_mistral(
            caption_prompt, 
            "Caption", 
            max_tokens=20  # Reduced tokens to prevent long output
        ).strip().split('\n')[0]  # Take only the first line to ensure brevity
        
        illustration = {
            "url": image_url if image_url else "https://example.com/default_image.jpg",
            "caption": caption if caption else f"Illustration {section['chapter_number']}"
        }
        
        illustrations.append(illustration)
        logging.info(f"Generated illustration: {illustration}")

    return illustrations




@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """Handles the story and PDF generation request asynchronously."""
    try:
        # ✅ Get request data
        data = request.get_json()
        logging.info(f"Received Data: {data}")  # Debugging

        # ✅ Extract Language Fields - MOVED TO TOP
        story_language = data.get('story-language', 'English').lower()  # Ensure story_language is assigned
        selected_language = story_language if story_language else "english"

        # ✅ Predefined Chapter Labels
        chapter_labels = {
            "english": "Chapter",
            "french": "Chapitre",
            "spanish": "Capítulo",
            "german": "Kapitel"
        }

        # ✅ Assign Chapter Label (Translate if necessary)
        chapter_label = chapter_labels.get(selected_language)
        if not chapter_label:
            chapter_label = translate_with_mistral("Chapter", selected_language)

        # ✅ Extract Other Story Fields
        child_name = data.get('childName', 'child')
        age = data.get('age', 7)
        character_type = data.get('character-type', 'Boy')
        custom_character = data.get('custom-character', None)
        interests = data.get('interests', 'adventures')

        # ✅ Ensure "moralLesson" is always a list
        moral_lesson = data.get("moralLesson", [])
        if isinstance(moral_lesson, str):  # Convert single values into a list
            moral_lesson = [moral_lesson]

        toggle_customization = data.get('toggle-customization', 'no').strip().lower() == 'yes'
        story_genre = data.get('story-genre', 'Fantasy')
        story_tone = data.get('story-tone', 'Lighthearted')
        surprise_ending = str(data.get('surprise-ending', 'false')).strip().lower() == 'true'
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

        if moral_lesson:
            moral_lessons_text = ", ".join(moral_lesson)  # Convert list to a readable string
            prompt += f" The story should teach the moral lessons of {moral_lessons_text}."

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
            if custom_bilingual_language:
                prompt += f" The story should be written in both English and {custom_bilingual_language}."
            elif bilingual_language and bilingual_language.lower() != "english":
                prompt += f" The story should be written in both English and {bilingual_language}."
        
        # ✅ Handle Custom Story Language
        elif story_language and story_language.lower() != "english":
            if story_language.lower() == "other-language" and custom_language:
                prompt += f" The story should be written in {custom_language}."
            else:
                prompt += f" The story should be written in {story_language}."

        log_memory_usage("Before Mistral API")

        # ✅ Log the prompt in the console
        logging.info(f"📝 Full AI Prompt:\n{prompt}\n")

        # ✅ Generate the Full Story
        full_story = generate_story_mistral(prompt, chapter_label, max_tokens=800)
        logging.info("Story generated successfully.")

        # ✅ Split into Sections
        sections = split_story_into_sections(full_story,chapter_label)
        logging.info(f"Story split into {len(sections)} sections.")

        # ✅ Generate Images for Each Section
        illustrations = generate_image_per_section(sections, story_language) # [] for empty

        log_memory_usage("After Mistral API")
        logging.info("Story generated successfully.")

        # ✅ Load and render HTML template
        with open("story_template.html") as template_file:
            template = Template(template_file.read())

        rendered_html = template.render(
            title=f"A Personalized Story for {child_name}",
            author=child_name,
            content=full_story,
            sections=sections,
            illustrations=illustrations,
            age=int(age),
            chapter_label=chapter_label 
        )
        
        logging.info("Rendering PDF with WeasyPrint...")
        log_memory_usage("Before PDF Generation")

        # ✅ Define PDF filename **BEFORE** starting Celery task
        pdf_filename = f"{child_name.strip().replace(' ', '_')}_story.pdf"  # ✅ Ensure clean filename
        logging.info(f"📂 Using PDF filename: {pdf_filename}")  # ✅ Debugging log

        # ✅ Run PDF generation as a background Celery task
        task = generate_pdf_task.delay(rendered_html, pdf_filename)
        logging.info(f"✅ Celery Task Queued: Task ID {task.id} with filename {pdf_filename}")

        pdf_url = f"https://story-backend-g7he.onrender.com/download/{pdf_filename}"

        return jsonify({
            "status": "pending",
            "message": "PDF is being generated.",
            "task_id": task.id,  # ✅ Send Task ID so the user can check progress
            "pdf_url": pdf_url  # ✅ This will be valid once the task completes
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
    """
    Endpoint to serve the generated PDF file, ensuring it is retrieved from the shared directory.
    """

    # Define shared directory where PDFs are stored
    pdf_dir = "/home/render/pdfs"
    sanitized_filename = filename.strip().replace(' ', '_')
    pdf_path = os.path.join(pdf_dir, sanitized_filename)  # ✅ Ensure filename is formatted correctly

    logging.info(f"🔍 Flask is searching for PDF: {pdf_path}")

    # Check if the file exists before attempting to serve it
    if not os.path.exists(pdf_path):
        logging.error(f"❌ PDF not found at: {pdf_path}")
        return jsonify({"status": "error", "message": f"File not found: {filename}"}), 404

    logging.info(f"✅ Serving PDF: {pdf_path}")
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=True)


# ✅ Ensure this runs at the bottom of your script (if applicable)
if __name__ == "__main__":
    app.run(debug=True)
