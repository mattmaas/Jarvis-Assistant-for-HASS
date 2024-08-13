from flask import Flask, request, jsonify
from voice_assistant import JarvisAssistant

app = Flask(__name__)
assistant = JarvisAssistant('config.ini')

@app.route('/api/type_string', methods=['POST'])
def type_string():
    data = request.json
    text = data.get('text')
    if text:
        assistant.handle_home_assistant_command('type_string', text)
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "No text provided"}), 400

@app.route('/api/start_listening', methods=['POST'])
def start_listening():
    assistant.start()
    return jsonify({"status": "success", "message": "Started listening"}), 200

@app.route('/api/stop_listening', methods=['POST'])
def stop_listening():
    assistant.stop()
    return jsonify({"status": "success", "message": "Stopped listening"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
