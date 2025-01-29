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
 
app = Flask(__name__)

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


def generate_story_mistral(prompt):
    """Generate a story using Mistral API (via OpenRouter)."""
    try:
        url = "https://api.mistral.ai/v1/chat/completions"  # Correct Mistral API
        headers = {"Authorization": f"Bearer {API_KEYS['mistral'].strip()}", "Content-Type": "application/json"}
        payload = {
            "model": "mistral-medium",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 75  # Optimize for cost & memory
        }

        logging.info("Calling Mistral API for story generation...")
        response = requests.post(url, json=payload, headers=headers)
        response_json = response.json()

        if "choices" in response_json and response_json["choices"]:
            return response_json["choices"][0]["message"]["content"]
        else:
            logging.error(f"Mistral API Error: {response_json}")
            return "Error generating story."

    except Exception as e:
        logging.error(f"Error calling Mistral API: {str(e)}")
        return "Error generating story."


def generate_image(prompt):
    """Generate an image using Replicate's Stable Diffusion 3 model."""
    model_version = "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4"
    # model_version = "stability-ai/stable-diffusion-3"
    try:
        input_data = {
            "prompt": prompt,
            "width": 128,  # Lower resolution for memory optimization
            "height": 128
        }

        logging.info(f"Calling Stable Diffusion with prompt: {prompt}")
        output = replicate_client.run(model_version, input=input_data)

        if not output or len(output) == 0:
            raise ValueError("Replicate API did not return a valid image URL.")

        logging.info(f"Generated Image URL: {output[0]}")
        return output[0]

    except Exception as e:
        logging.error(f"Error generating image: {str(e)}")
        return None  # Return None instead of crashing


@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """Handles the story and PDF generation request."""
    try:
        # Get request data
        data = request.get_json()
        child_name = data.get('childName', 'child')
        age = data.get('age', 7)
        interests = data.get('interests', 'adventures')
        moral_lesson = data.get('moralLesson', 'kindness')

        # Construct the prompt
        prompt = (f"Write a short children's story for a {age}-year-old named {child_name}. "
                  f"The story should include their interests: {interests}. "
                  f"The story should teach the moral lesson: {moral_lesson}. "
                  f"Make it fun, engaging, and child-appropriate.")

        log_memory_usage("Before Mistral API")

        # ✅ Call Mistral API (Story Generation)
        story_content = generate_story_mistral(prompt)

        log_memory_usage("After Mistral API")

        logging.info("Story generated successfully.")

        # ✅ Generate illustration
        illustration_prompt = f"A children's storybook illustration for: {story_content[:50]}..."
        logging.info("Calling Replicate API for image generation...")

        log_memory_usage("Before Replicate API")
        illustration_url = generate_image(illustration_prompt)
        log_memory_usage("After Replicate API")

        if not illustration_url:
            illustration_url = "https://example.com/default_image.jpg"  # Fallback image

        logging.info(f"Illustration URL: {illustration_url}")

        # ✅ Load and render HTML template
        with open("story_template.html") as template_file:
            template = Template(template_file.read())

        rendered_html = template.render(
            title=f"A Personalized Story for {child_name}",
            author=child_name,
            content=story_content,
            illustrations=[illustration_url]
        )

        logging.info("Rendering PDF with WeasyPrint...")
        log_memory_usage("Before PDF Generation")

        # ✅ Generate PDF using a temporary file (reduces memory pressure)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            HTML(string=rendered_html).write_pdf(temp_pdf.name)
            temp_pdf_path = temp_pdf.name

        log_memory_usage("After PDF Generation")

        # ✅ Send the generated PDF as a response
        response = send_file(
            temp_pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{child_name}_story.pdf"
        )

        # ✅ Clean up memory-heavy variables
        del story_content, illustration_url, rendered_html
        gc.collect()
        log_memory_usage("After Request Cleanup")

        return response

    except MemoryError:
        logging.error("Memory limit exceeded! Consider reducing API responses or upgrading memory.")
        return jsonify({"status": "error", "message": "Server ran out of memory. Try reducing input size or upgrading the plan."}), 500

    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        gc.collect()
