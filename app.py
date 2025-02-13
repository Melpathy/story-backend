from celery import Celery
from flask import Flask, request, jsonify, send_file, redirect
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, Template
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import os
import gc
import logging
import replicate
from flask_cors import CORS

with open("templates/story_template.html", "r", encoding="utf-8") as f:
    template_str = f.read()
template = Template(template_str)

# Import our new modules
from config import CELERY_CONFIG, FLASK_CONFIG, STORAGE_CONFIG, API_CONFIG, BASE_URLS
from utils import sanitize_filename, get_s3_key, log_memory_usage, build_story_prompt
from story_generator import StoryGenerator
from language_handler import get_language_config, format_language_strings

# Update in app.py
app = Flask(__name__)

# Celery setup - simplified to use your existing config
app.config['CELERY_BROKER_URL'] = CELERY_CONFIG['BROKER_URL']
app.config['CELERY_RESULT_BACKEND'] = CELERY_CONFIG['RESULT_BACKEND']
app.config['MAX_CONTENT_LENGTH'] = FLASK_CONFIG['MAX_CONTENT_LENGTH']

# Initialize Celery with your Redis URL
celery = Celery(app.name, 
                broker=CELERY_CONFIG['BROKER_URL'],
                backend=CELERY_CONFIG['RESULT_BACKEND'])

# Set retry on startup
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
    Args:
        bucket_name (str): Name of the S3 bucket
        s3_key (str): Key of the object in S3
        expiration (int): URL expiration time in seconds (default: 1 hour)
    """
    try:
        # Ensure expiration is an integer
        expiration = int(expiration)
        
        # Generate the pre-signed URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key
            },
            ExpiresIn=expiration
        )
        logging.info(f"✅ Generated pre-signed URL with {expiration}s expiration")
        return presigned_url
    except ValueError as e:
        logging.error(f"❌ Invalid expiration value: {str(e)}")
        # Fallback to 1 hour if there's an issue with the expiration value
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
        # Create temp directory if it doesn't exist
        pdf_dir = "/tmp"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, pdf_filename.strip().replace(' ', '_'))

        # Generate PDF
        HTML(string=html_content).write_pdf(pdf_path)
        logging.info(f"✅ PDF successfully saved: {pdf_path}")

        # Get S3 bucket name
        bucket_name = os.getenv("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("❌ ERROR: S3_BUCKET_NAME environment variable is missing!")

        # Generate S3 key
        date_prefix = datetime.utcnow().strftime('%Y-%m-%d')
        s3_key = f"pdfs/{date_prefix}/{pdf_filename.strip().replace(' ', '_')}"

        # Upload to S3 with specific content headers
        s3_client.upload_file(
            pdf_path, 
            bucket_name, 
            s3_key, 
            ExtraArgs={
                'ContentType': 'application/pdf',
                'ContentDisposition': 'inline'  # This tells browsers to display the PDF
            }
        )

        # Generate pre-signed URL
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
    
    # Get language configuration
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

def handle_language_configs(data):
    """
    Handle both primary and bilingual language configurations.
    Returns primary and secondary language configs if bilingual mode is enabled.
    """
    # Get primary language configuration
    story_language = data.get('story-language', 'English').lower()
    custom_language = data.get('custom-language', None)
    primary_config = get_language_config(story_language, custom_language)
    
    # Check if bilingual mode is enabled - handle multiple possible values
    bilingual_mode = data.get('bilingual-mode', '').lower()
    if bilingual_mode in ['true', 'on', '1', 'yes']:
        bilingual_language = data.get('bilingual-language', '').lower()
        bilingual_custom = data.get('custom-bilingual-language', None)
        logging.info(f"Bilingual mode enabled. Language: {bilingual_language}")
        secondary_config = get_language_config(bilingual_language, bilingual_custom)
        return primary_config, secondary_config
    
    logging.info("Bilingual mode disabled")
    return primary_config, None

@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """Handle story and PDF generation request."""
    
    formatted_primary = {"error_message": "An error occurred while generating your story."}

    try:
        # Get request data
        data = request.get_json()
        story_length = data.get('story_length', 'short')
        logging.info(f"Received Data: {data}")

        # Get language configurations
        primary_lang_config, secondary_lang_config = handle_language_configs(data)
        
        # Format language strings
        context = {
            'name': data.get('childName', 'child'),
            'author': data.get('childName', 'child')
        }
      
        # Format strings for both languages
        formatted_primary = format_language_strings(primary_lang_config, context)
        formatted_secondary = None
        if secondary_lang_config:
            formatted_secondary = format_language_strings(secondary_lang_config, context)
          
        # Build story prompt
        prompt = build_story_prompt(data, formatted_primary)
        logging.info(f"📝 Full AI Prompt:\n{prompt}\n")

        # Generate story in primary language with story length
        log_memory_usage("Before Story Generation")
        primary_story = story_generator.generate_story(
            prompt, 
            formatted_primary['chapter_label'],
            story_length=story_length  # Pass story length here
        )

        # Handle bilingual content if enabled
        if data.get('bilingual-mode') == 'true':
            bilingual_format = data.get('bilingual-format', 'AABB')
            secondary_story = story_generator.translate_story(
                primary_story,
                data.get('bilingual-language', ''),
                bilingual_format
            )

      
        # Split content based on format
            if bilingual_format == 'AABB':
                sections = story_generator.split_into_parallel_sections(
                    primary_story,
                    secondary_story,
                    formatted_primary['chapter_label'],
                    formatted_secondary['chapter_label']
                )
            else:  # ABAB format
                sections = story_generator.split_into_sentence_pairs(
                    primary_story,
                    secondary_story
                )
        else:
            sections = story_generator.split_into_sections(
                primary_story, 
                formatted_primary['chapter_label']
            )
          
        log_memory_usage("Before PDF Generation")
        rendered_html = template.render(
            title=formatted_primary['story_title'],
            author=formatted_primary['by_author'],
            bilingual_mode=data.get('bilingual-mode') == 'true',
            bilingual_format=data.get('bilingual-format', 'AABB'),
            sections=sections,
            chapter_label=formatted_primary['chapter_label'],
            chapter_label_second_language=formatted_secondary['chapter_label'] if formatted_secondary else None,
            end_text=formatted_primary['end_text'],
            end_text_second_language=formatted_secondary['end_text'] if formatted_secondary else None,
            primary_language=data.get('story-language', 'English'),
            second_language=data.get('bilingual-language') if data.get('bilingual-mode') == 'true' else None,
            illustration_label=formatted_primary['illustration_label'],
            no_illustrations_text=formatted_primary['no_illustrations'],
            age=int(data.get('age', 7))
        )


        # Queue PDF generation task
        pdf_filename = f"{sanitize_filename(data.get('childName', 'child'))}_story.pdf"
        task = generate_pdf_task.delay(rendered_html, pdf_filename)
        
        return jsonify({
            "status": "pending",
            "message": formatted_primary['loading_message'],
            "task_id": task.id,
            "pdf_url": f"{BASE_URLS['DOWNLOAD']}/{pdf_filename}"
        })

    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": formatted_primary.get('error_message', str(e))
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

        # Generate S3 key
        date_prefix = datetime.utcnow().strftime('%Y-%m-%d')
        s3_key = f"pdfs/{date_prefix}/{filename.strip().replace(' ', '_')}"

        # Generate pre-signed URL with inline content disposition
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
