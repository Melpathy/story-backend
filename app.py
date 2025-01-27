from flask import Flask, request, jsonify, send_file
from weasyprint import HTML
from jinja2 import Template
import os
from io import BytesIO
from openai import OpenAI
import replicate
import logging

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

def generate_image(prompt):
    """
    Generate an image using Replicate's Stable Diffusion model.
    """
    # Full model version ID
    model_version = "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff76822a1affe01863cbe77e4"

    try:
        # Call the Replicate API to generate the image
        output = replicate_client.run(
            model_version,
            input={
                "prompt": prompt,
                "scheduler": "K_EULER"  # Optional field, included for stability
            }
        )

        logging.info("Image generated successfully.")
        return output[0]  # Return the first generated image URL

    except Exception as e:
        logging.error(f"Error generating image: {str(e)}")
        raise ValueError("Failed to generate illustration. Please try again.")

@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    data = request.get_json()

    # Extract user input from the JSON body
    child_name = data.get('childName', 'child')
    age = data.get('age', 7)
    interests = data.get('interests', 'adventures')
    moral_lesson = data.get('moralLesson', 'kindness')

    # Construct the prompt
    prompt = (f"Write a short children's story for a {age}-year-old named {child_name}. "
              f"The story should include their interests: {interests}. "
              f"The story should teach the moral lesson: {moral_lesson}. "
              f"Make it fun, engaging, and child-appropriate.")

    try:
        # Call the DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a creative story generator for children."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,  # Limit tokens (about ~100 words)
            stream=False
        )

        # Safeguard for missing content
        if not hasattr(response, 'choices') or not response.choices:
            raise ValueError("The DeepSeek API response does not contain 'choices'.")

        if not hasattr(response.choices[0].message, 'content'):
            raise ValueError("The DeepSeek API response does not contain 'message.content'.")

        # Extract the generated story
        story_content = response.choices[0].message.content
        logging.info("Story generated successfully.")

        # Generate an illustration for the story
        illustration_prompt = f"An illustration for this story: {story_content[:50]}... in a children's storybook style."
        illustration_url = generate_image(illustration_prompt)
        logging.info(f"Illustration URL: {illustration_url}")

        # Load the HTML template and populate it
        with open("story_template.html") as template_file:
            template = Template(template_file.read())

        rendered_html = template.render(
            title=f"A Personalized Story for {child_name}",
            author=child_name,
            content=story_content,
            illustrations=[illustration_url]  # Include the generated image URL
        )

        # Generate the PDF
        pdf_buffer = BytesIO()
        HTML(string=rendered_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # Send the generated PDF as a response
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{child_name}_story.pdf"
        )

    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
