from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    child_name = data.get('childName')
    age = data.get('age')
    interests = data.get('interests')
    moral_lesson = data.get('moralLesson')

    print("Received data:", data)

    # Return a mock JSON response for now
    return jsonify({
        "status": "success",
        "message": f"Story generation for {child_name} complete (mock)."
    }), 200

if __name__ == '__main__':
    # debug=True helps for development
    app.run(debug=True, port=5000)
