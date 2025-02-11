# Add this import at the top with your other imports
from language_handler import get_language_config, format_language_strings

# Find your existing /api/generate-story route and update these parts:
@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    try:
        # Your existing code...
        data = request.get_json()
        
        # Replace your language handling code with this:
        story_language = data.get('story-language', 'English').lower()
        custom_language = data.get('custom-language', None)
        
        # Get language configuration
        lang_config = get_language_config(story_language, custom_language)
        
        # Format language strings with context
        context = {
            'name': data.get('childName', 'child'),
            'author': data.get('childName', 'child')
        }
        formatted_lang = format_language_strings(lang_config, context)

        # Your existing code for extracting other fields...
        child_name = data.get('childName', 'child')
        age = data.get('age', 7)
        # ... (keep all your other field extractions)

        # Update your template rendering to use the new language strings:
        rendered_html = template.render(
            title=formatted_lang['story_title'],
            author=formatted_lang['by_author'],
            content=full_story,
            sections=sections,
            illustrations=illustrations,
            age=int(age),
            chapter_label=formatted_lang['chapter_label'],
            end_text=formatted_lang['end_text'],
            no_illustrations_text=formatted_lang['no_illustrations']
        )

        # Rest of your code remains the same...
        
        return jsonify({
            "status": "pending",
            "message": formatted_lang['loading_message'],
            "task_id": task.id,
            "pdf_url": f"https://story-backend-g7he.onrender.com/download/{pdf_filename}"
        })

    except Exception as e:
        logging.error(f"Error in generate_story: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": formatted_lang.get('error_message', str(e))
        }), 500
