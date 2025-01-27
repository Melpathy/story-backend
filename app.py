from flask import Flask, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)

# Load the DeepSeek API key from environment variables
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("DeepSeek API key not found. Set the DEEPSEEK_API_KEY environment variable.")

# Initialize the DeepSeek (OpenAI-compatible) client
client = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")

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
            stream=False
        )

        # Extract the generated story
        story = response['choices'][0]['message']['content']

        return jsonify({
            "status": "success",
            "story": story
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
