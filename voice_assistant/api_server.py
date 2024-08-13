from flask import Flask, request, jsonify
from voice_assistant import VoiceAssistant

app = Flask(__name__)
assistant = VoiceAssistant('config.ini')

@app.route('/api/type_string', methods=['POST'])
def type_string():
    data = request.json
    text = data.get('text')
    if text:
        assistant.handle_home_assistant_command('type_string', text)
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "No text provided"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
