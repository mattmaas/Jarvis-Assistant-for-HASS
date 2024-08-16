from flask import Flask, request, jsonify, Response
import os
import subprocess
import json
import threading
import logging

app = Flask(__name__)
assistant = None

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_assistant(assistant_instance):
    global assistant
    assistant = assistant_instance

def run_flask_server():
    app.run(host='0.0.0.0', port=5000, threaded=True)

@app.route('/api/type_string', methods=['POST'])
def type_string():
    text = request.data.decode('utf-8')
    if text:
        assistant.handle_home_assistant_command('type_string', text)
        return Response("Success", mimetype='text/plain'), 200
    else:
        return Response("Error: No text provided", mimetype='text/plain'), 400

@app.route('/api/launch_file', methods=['POST'])
def launch_file():
    filename = request.data.decode('utf-8')
    if not filename:
        return Response("Error: No filename provided", mimetype='text/plain'), 400

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
            return Response(f"Error: File or nickname '{filename}' not found", mimetype='text/plain'), 404

    try:
        subprocess.Popen(filename, shell=True)
        return Response(f"File {filename} launched successfully", mimetype='text/plain'), 200
    except Exception as e:
        return Response(f"Error launching file: {str(e)}", mimetype='text/plain'), 500

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
    logger.debug("Received start_listening request")
    assistant.start()
    logger.debug("Started listening")
    return Response("Started listening", mimetype='text/plain'), 200

@app.route('/api/stop_listening', methods=['POST'])
def stop_listening():
    logger.debug("Received stop_listening request")
    assistant.stop()
    logger.debug("Stopped listening")
    return Response("Stopped listening", mimetype='text/plain'), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
