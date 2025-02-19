from celery import Celery
from flask import Flask, request, jsonify, send_file, redirect
from weasyprint import HTML
from jinja2 import Template
from datetime import datetime
from language_handler import get_language_config, format_language_strings, translate_with_mistral
import boto3
from botocore.exceptions import NoCredentialsError
import os
import gc
import logging
import replicate
from flask_cors import CORS

# Import our new modules
from config import CELERY_CONFIG, FLASK_CONFIG, STORAGE_CONFIG, API_CONFIG, BASE_URLS
from utils import sanitize_filename, get_s3_key, log_memory_usage, build_story_prompt
from story_generator import StoryGenerator

# Initialize Flask app
app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = CELERY_CONFIG['BROKER_URL']
app.config['CELERY_RESULT_BACKEND'] = CELERY_CONFIG['RESULT_BACKEND']
app.config['MAX_CONTENT_LENGTH'] = FLASK_CONFIG['MAX_CONTENT_LENGTH']

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], 
                backend=app.config['CELERY_RESULT_BACKEND'])
celery.conf.broker_connection_retry_on_startup = CELERY_CONFIG['BROKER_CONNECTION_RETRY_ON_STARTUP']

# Initialize CORS
CORS(app, resources={r"/*": {"origins": FLASK_CONFIG['CORS_ORIGINS']}}, supports_credentials=True)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize S3 Client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)

# Initialize API keys
API_KEYS = {
    "mistral": os.getenv("MISTRAL_API_KEY"),
    "replicate": os.getenv("REPLICATE_API_TOKEN")
}

# Validate API Keys
if not all(API_KEYS.values()):
    raise ValueError("Missing required API keys. Check environment variables.")

# Initialize Replicate client
replicate_client = replicate.Client(api_token=API_KEYS["replicate"])

# Initialize Story Generator
story_generator = StoryGenerator(API_KEYS["mistral"], replicate_client)

def generate_presigned_url(bucket_name, s3_key, expiration=3600):
    """
    Generate a temporary pre-signed URL for accessing private PDFs on S3.
    """
    try:
        expiration = int(expiration)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiration
        )
        logging.info(f"✅ Generated pre-signed URL with {expiration}s expiration")
        return presigned_url
    except ValueError as e:
        logging.error(f"❌ Invalid expiration value: {str(e)}")
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=3600
        )
    except NoCredentialsError:
        logging.error("❌ AWS credentials not found")
        return None
    except Exception as e:
        logging.error(f"❌ Error generating pre-signed URL: {str(e)}")
        return None

@app.after_request
def add_headers(response):
    """Add CORS headers to response."""
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Credentials": "true"
    })
    return response

@celery.task
def generate_pdf_task(html_content, pdf_filename):
    """Generate PDF, upload to S3, and return a temporary pre-signed URL."""
    try:
        pdf_dir = "/tmp"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, pdf_filename.strip().replace(' ', '_'))
        HTML(string=html_content).write_pdf(pdf_path)
        logging.info(f"✅ PDF successfully saved: {pdf_path}")

        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("❌ ERROR: S3_BUCKET_NAME environment variable is missing!")

        date_prefix = datetime.utcnow().strftime('%Y-%m-%d')
        s3_key = f"pdfs/{date_prefix}/{pdf_filename.strip().replace(' ', '_')}"

        s3_client.upload_file(
            pdf_path, 
            bucket_name, 
            s3_key, 
            ExtraArgs={
                'ContentType': 'application/pdf',
                'ContentDisposition': 'inline'
            }
        )

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key,
                'ResponseContentType': 'application/pdf',
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=3600
        )

        logging.info(f"✅ Pre-signed URL generated: {presigned_url}")
        return presigned_url

    except Exception as e:
        logging.error(f"❌ PDF Generation Failed: {str(e)}")
        return None

@app.route('/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Check Celery task status and return S3 URL if ready."""
    task = generate_pdf_task.AsyncResult(task_id)
    lang_config = get_language_config('english')
    formatted_lang = format_language_strings(lang_config, {'name': '', 'author': ''})

    if task.state == "PENDING":
        return jsonify({
            "status": "pending", 
            "message": formatted_lang['loading_message']
        })

    elif task.state == "SUCCESS":
        s3_url = task.result
        if s3_url:
            return jsonify({
                "status": "completed",
                "pdf_url": s3_url,
                "message": formatted_lang['success_message']
            })
        return jsonify({
            "status": "error", 
            "message": formatted_lang['error_message']
        }), 500

    return jsonify({
        "status": task.state, 
        "message": formatted_lang['processing_message']
    })

@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """Handle story and PDF generation request."""
    try:
        data = request.get_json()
        story_length = data.get('story_length', 'short')
        logging.info(f"Received Data: {data}")

        # Language configuration
        story_language = data.get('story-language', 'English').lower()
        custom_language = data.get('custom-language', None)
        lang_config = get_language_config(story_language, custom_language)
        context = {
            'name': data.get('childName', 'child'),
            'author': data.get('childName', 'child')
        }
        formatted_lang = format_language_strings(lang_config, context)
    
        # Build prompt and generate story
        prompt = build_story_prompt(data, formatted_lang)
        logging.info(f"📝 Full AI Prompt:\n{prompt}\n")
        log_memory_usage("Before Story Generation")
        full_story = story_generator.generate_story(
            prompt, 
            formatted_lang['chapter_label'],
            story_length=story_length
        )
    
        # Split story into sections (each section should have its own title and content)
        sections = story_generator.split_into_sections(full_story, formatted_lang['chapter_label'])
        illustrations = []  # No illustrations for now
    
        # Handle bilingual mode: translate chapter title and content separately
        bilingual_mode = data.get('bilingual-mode') == 'true'
        if bilingual_mode:
            target_language = (data.get('custom-bilingual-language') or data.get('bilingual-language')).strip()
            bilingual_format = data.get('bilingual-format', '').strip().upper()
            if bilingual_format == "AABB":
                for section in sections:
                    # Translate title and content separately
                    section['translated_title'] = translate_with_mistral(section.get('title', ''), target_language)
                    section['translated_content'] = translate_with_mistral(section.get('content', ''), target_language)
    
        # Render PDF HTML
        with open("story_template.html") as template_file:
            template = Template(template_file.read())
    
        rendered_html = template.render(
            title=formatted_lang['story_title'],
            author=formatted_lang['by_author'],
            content=full_story,
            sections=sections,
            illustrations=illustrations,
            age=int(data.get('age', 7)),
            chapter_label=formatted_lang['chapter_label'],
            end_text=formatted_lang['end_text'],
            no_illustrations_text=formatted_lang['no_illustrations'],
            bilingual_mode=bilingual_mode
        )
    
        pdf_filename = f"{sanitize_filename(data.get('childName', 'child'))}_story.pdf"
        task = generate_pdf_task.delay(rendered_html, pdf_filename)
        
        return jsonify({
            "status": "pending",
            "message": formatted_lang['loading_message'],
            "task_id": task.id,
            "pdf_url": f"{BASE_URLS['DOWNLOAD']}/{pdf_filename}"
        })
    
    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": formatted_lang.get('error_message', str(e))
        }), 500
    
    finally:
        gc.collect()
        log_memory_usage("After Request Cleanup")

@app.route('/download/<filename>')
def download_file(filename):
    """Redirect to S3 pre-signed URL for PDF viewing."""
    try:
        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable is missing!")

        date_prefix = datetime.utcnow().strftime('%Y-%m-%d')
        s3_key = f"pdfs/{date_prefix}/{filename.strip().replace(' ', '_')}"
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key,
                'ResponseContentType': 'application/pdf',
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=3600
        )

        if presigned_url:
            return redirect(presigned_url)
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to generate pre-signed URL"
            }), 500

    except Exception as e:
        logging.error(f"❌ Error serving PDF: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
