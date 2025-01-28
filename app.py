from flask import Flask, request, jsonify, send_file
from weasyprint import HTML
from jinja2 import Template
import os
import tempfile  # Use temporary files instead of keeping data in memory
from io import BytesIO
from openai import OpenAI
import replicate
import logging
import psutil
import gc  # For memory cleanup

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load the DeepSeek API key from environment variables
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("DeepSeek API key not found. Set the DEEPSEEK_API_KEY environment variable.")

# Load the Replicate API key from environment variables
replicate_api_key = os.getenv("REPLICATE_API_TOKEN")
if not replicate_api_key:
    raise ValueError("Replicate API key not found. Set the REPLICATE_API_TOKEN environment variable.")

# Initialize the DeepSeek (OpenAI-compatible) client
client = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")

# Initialize the Replicate client
replicate_client = replicate.Client(api_token=replicate_api_key)


def log_memory_usage(stage):
    """Logs the current memory usage at different stages."""
    process = psutil.Process()
    mem_info = process.memory_info()
    logging.info(f"[{stage}] Memory Usage: {mem_info.rss / (1024 * 1024):.2f} MB")  # Convert bytes to MB


def generate_image(prompt):
    """Generate an image using Replicate's Stable Diffusion 3 model."""
    model_version = "stability-ai/stable-diffusion-3"

    try:
        # Reduce image size for memory optimization
        input_data = {
            "prompt": prompt,
            "width": 128,  # Reduce from 256
            "height": 128  # Reduce from 256
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

        log_memory_usage("Before DeepSeek API")

        # Call the DeepSeek API (Story Generation)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a creative story generator for children."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=75,  # Reduce from 100 to 75 to lower memory usage
            stream=False
        )

        log_memory_usage("After DeepSeek API")

        if not response.choices or not hasattr(response.choices[0].message, 'content'):
            raise ValueError("DeepSeek API did not return valid story content.")

        story_content = response.choices[0].message.content
        logging.info("Story generated successfully.")

        # Generate illustration
        illustration_prompt = f"A children's storybook illustration for: {story_content[:50]}..."
        logging.info("Calling Replicate API for image generation...")

        log_memory_usage("Before Replicate API")
        illustration_url = generate_image(illustration_prompt)
        log_memory_usage("After Replicate API")

        if not illustration_url:
            illustration_url = "https://example.com/default_image.jpg"  # Fallback image

        logging.info(f"Illustration URL: {illustration_url}")

        # Load and render HTML template
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

        # Generate PDF using a temporary file (reduces memory pressure)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            HTML(string=rendered_html).write_pdf(temp_pdf.name)
            temp_pdf_path = temp_pdf.name

        log_memory_usage("After PDF Generation")

        # Send the generated PDF as a response
        response = send_file(
            temp_pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{child_name}_story.pdf"
        )

        # Clean up memory-heavy variables
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
