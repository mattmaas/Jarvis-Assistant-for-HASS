from flask import Flask, request, jsonify
from voice_assistant import JarvisAssistant
import os
import subprocess
import json
import threading

app = Flask(__name__)
assistant = JarvisAssistant('config.ini')

def run_flask_server():
    app.run(host='0.0.0.0', port=5000, threaded=True)

@app.route('/api/type_string', methods=['POST'])
def type_string():
    data = request.json
    text = data.get('text')
    if text:
        assistant.handle_home_assistant_command('type_string', text)
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "No text provided"}), 400

@app.route('/api/launch_file', methods=['POST'])
def launch_file():
    data = request.json
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    # Check if the filename is a nickname
    nicknames = load_nicknames()
    if filename in nicknames:
        filename = nicknames[filename]
    elif not os.path.exists(filename):
        # If it's not a nickname and not an existing file, check if it's a relative path
        if not os.path.isabs(filename):
            filename = os.path.join(os.path.dirname(__file__), filename)
        
        # If it still doesn't exist, return an error
        if not os.path.exists(filename):
            return jsonify({"error": f"File or nickname '{filename}' not found"}), 404

    try:
        subprocess.Popen(filename, shell=True)
        return jsonify({"message": f"File {filename} launched successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Error launching file: {str(e)}"}), 500

@app.route('/api/add_file_nickname', methods=['POST'])
def add_file_nickname():
    data = request.json
    nickname = data.get('nickname')
    filename = data.get('filename')
    if not nickname or not filename:
        return jsonify({"error": "Both nickname and filename are required"}), 400

    nicknames = load_nicknames()
    nicknames[nickname] = filename
    save_nicknames(nicknames)

    return jsonify({"message": f"Nickname '{nickname}' added for file '{filename}'"}), 200

def load_nicknames():
    nickname_file = os.path.join(os.path.dirname(__file__), 'file_nicknames.json')
    if os.path.exists(nickname_file):
        with open(nickname_file, 'r') as f:
            return json.load(f)
    return {}

def save_nicknames(nicknames):
    nickname_file = os.path.join(os.path.dirname(__file__), 'file_nicknames.json')
    with open(nickname_file, 'w') as f:
        json.dump(nicknames, f, indent=2)
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
