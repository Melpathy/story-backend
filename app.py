from flask import Flask, request, jsonify, send_file
from weasyprint import HTML
from jinja2 import Template
import os
from io import BytesIO
from openai import OpenAI
import replicate

app = Flask(__name__)

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
    model = "stability-ai/stable-diffusion"
    version = "latest"

    # Call the Replicate API to generate the image
    output = replicate_client.run(
        f"{model}:{version}",
        input={"prompt": prompt}
    )

    return output[0]  # Returns the image URL

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

        # Generate an illustration for the story
        illustration_prompt = f"An illustration for this story: {story_content[:50]}... in a children's storybook style."
        illustration_url = generate_image(illustration_prompt)

        # Load the HTML template and populate it
        with open("story_template.html") as template_file:
            template = Template(template_file.read())

        rendered_html = template.render(
            title="A Personalized Story",
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
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
