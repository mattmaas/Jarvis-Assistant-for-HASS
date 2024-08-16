import os
import sys
import shutil
import PyInstaller.__main__

def build_executable():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the spec file path
    spec_file = os.path.join(current_dir, "voice_assistant.spec")
    
    # Define the output directory as the current directory
    dist_dir = current_dir
    
    # Remove existing build and dist directories
    for dir_name in ['build', 'dist']:
        dir_path = os.path.join(current_dir, dir_name)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    
    # Create the PyInstaller command
    pyinstaller_args = [
        'main.py',
        '--name=VoiceAssistant',
        '--onefile',
        '--windowed',
        f'--distpath={dist_dir}',
        '--add-data=icon.png:.',
        '--add-data=config.ini:.',
        '--add-data=wakewords.json:.',
        '--add-data=file_nicknames.json:.',
        '--icon=icon.ico',
        '--hidden-import=websocket',
        '--hidden-import=pvporcupine',
        '--hidden-import=pyaudio',
        '--hidden-import=speech_recognition',
        '--hidden-import=openai',
        '--hidden-import=requests',
        '--hidden-import=pyautogui',
        '--hidden-import=openrgb_control',
    ]
    
    # Run PyInstaller
    PyInstaller.__main__.run(pyinstaller_args)
    
    print("Build process completed.")

if __name__ == "__main__":
    build_executable()
class JarvisAssistant:
    def __init__(self, config_path, sensitivity=0.5):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.access_key = self.config['PORCUPINE']['ACCESS_KEY']
        self.sensitivity = sensitivity
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False
        openai.api_key = self.config['OPENAI']['API_KEY']
        self.stt_provider = self.config['STT']['PROVIDER']
        self.ha_url = self.config['HOME_ASSISTANT']['URL']
        self.ha_token = self.config['HOME_ASSISTANT']['ACCESS_TOKEN']
        self.ha_pipeline = "jarvis_en"  # Set default pipeline
        self.ws = None
        self.message_id = 0  # Initialize message ID counter
        self.ws_lock = threading.Lock()  # Add a lock for thread-safe WebSocket operations
        self.wake_words = self._load_wake_words()
        self.rgb_control = OpenRGBControl()
        self.last_ping_time = 0
        self.ping_interval = 50  # Send a ping every 50 seconds
        self.reconnect_interval = 300  # Try to reconnect every 5 minutes if disconnected
        
        # Import and start the Flask server in a separate thread
        from api_server import run_flask_server, init_assistant
        init_assistant(self)
        self.flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        self.flask_thread.start()

    def _load_wake_words(self):
        try:
            with open('wakewords.json', 'r') as f:
                wake_words = json.load(f)
            if not isinstance(wake_words, dict):
                raise ValueError("Loaded JSON is not a dictionary")
            self.pipeline_keywords = {name: data.get('keywords', []) for name, data in wake_words.items()}
            return {name: {"id": data.get('id', name), "name": name} for name, data in wake_words.items()}
        except json.JSONDecodeError as e:
            self._debug_print(f"Error decoding JSON: {e}")
            return {}
        except Exception as e:
            self._debug_print(f"Error loading wake words: {e}")
            return {}

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._connect_to_home_assistant()  # Connect to Home Assistant when starting
            self._set_ice_profile()  # Load 'ice' profile
            threading.Thread(target=self._run).start()
            threading.Thread(target=self._keep_alive).start()  # Start keep-alive thread
        else:
            self._set_ice_profile()  # Ensure 'ice' profile is set when restarting

    def _set_ice_profile(self):
        max_retries = 3
        retry_delay = 60  # seconds

        for attempt in range(max_retries):
            try:
                self.rgb_control.set_profile("ice")
                self._debug_print("Successfully set 'ice' profile")
                return
            except Exception as e:
                self._debug_print(f"Error setting 'ice' profile (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    self._debug_print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self._debug_print("Failed to set 'ice' profile after all attempts")

    def stop(self):
        self.is_running = False
        self._disconnect_from_home_assistant()
        self.rgb_control.set_mic_color((255, 69, 0))  # Set to a more vibrant orange color (Red-Orange)

    def _run(self):
        try:
            self.porcupine = pvporcupine.create(access_key=self.access_key, keywords=["jarvis"], sensitivities=[self.sensitivity])
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )

            while self.is_running:
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    self._debug_print("Wake word 'Jarvis' detected")
                    self._play_chime()
                    self.rgb_control.set_mic_color((128, 0, 128))  # Set purple color
                    self._process_speech()
                    self.rgb_control.set_profile("ice")  # Load 'ice' profile after processing

        finally:
            if self.audio_stream:
                self.audio_stream.close()
            if self.pa:
                self.pa.terminate()
            if self.porcupine:
                self.porcupine.delete()

    def _keep_alive(self):
        while self.is_running:
            current_time = time.time()
            if current_time - self.last_ping_time > self.ping_interval:
                self._send_ping()
                self.last_ping_time = current_time
            
            if not self._check_websocket_connection():
                self._reconnect_to_home_assistant()
            
            time.sleep(1)  # Check every second

    def _send_ping(self):
        with self.ws_lock:
            if self.ws and self.ws.connected:
                try:
                    self.message_id += 1
                    ping_message = {
                        "type": "ping",
                        "id": self.message_id
                    }
                    self.ws.send(json.dumps(ping_message))
                    self._debug_print(f"Sent ping (ID: {self.message_id})")
                except Exception as e:
                    self._debug_print(f"Error sending ping: {str(e)}")
                    self._reconnect_to_home_assistant()

    def _reconnect_to_home_assistant(self):
        self._debug_print("Attempting to reconnect to Home Assistant...")
        self._disconnect_from_home_assistant()
        reconnect_success = self._connect_to_home_assistant()
        if reconnect_success:
            self._debug_print("Successfully reconnected to Home Assistant")
        else:
            self._debug_print("Failed to reconnect to Home Assistant")

    def _disconnect_from_home_assistant(self):
        with self.ws_lock:
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    self._debug_print(f"Error closing WebSocket: {str(e)}")
                finally:
                    self.ws = None

    def _process_speech(self):
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self._debug_print("Listening for command...")
                recognizer.dynamic_energy_threshold = True
                recognizer.energy_threshold = 300  # Lower value for increased sensitivity
                recognizer.pause_threshold = 1.5  # Increased pause threshold for longer pauses
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)

            try:
                if self.stt_provider == "google":
                    command = recognizer.recognize_google(audio, show_all=True)
                    if command:
                        best_guess = command['alternative'][0]['transcript']
                        self._debug_print(f"Command recognized: {best_guess}")
                        self._execute_command(best_guess)
                    else:
                        self._debug_print("Could not understand the command")
                elif self.stt_provider == "whisper":
                    try:
                        audio_data = audio.get_wav_data()
                        audio_file = io.BytesIO(audio_data)
                        audio_file.name = 'audio.wav'  # Add a name attribute to the BytesIO object
                        response = openai.Audio.transcribe("whisper-1", audio_file)
                        if response and 'text' in response:
                            command = response['text']
                            self._debug_print(f"Command recognized: {command}")
                            self._execute_command(command)
                        else:
                            self._debug_print("Could not understand the command")
                    except Exception as e:
                        self._debug_print(f"Error in Whisper transcription: {e}")
                        self._debug_print(f"Full exception details: {str(e)}")
                else:
                    self._debug_print("Invalid STT provider specified")
            except sr.UnknownValueError:
                self._debug_print("Could not understand the command")
            except sr.RequestError as e:
                self._debug_print(f"Could not request results; {e}")
        except sr.WaitTimeoutError:
            self._debug_print("No speech detected. Listening for wake word again.")
        except Exception as e:
            self._debug_print(f"An error occurred: {e}")

    def _select_pipeline(self, text: str) -> str:
        if self.ha_pipeline == "auto":
            words = text.lower().split()
            for pipeline_name, data in self.wake_words.items():
                keywords = self.pipeline_keywords.get(pipeline_name, [])
                if any(keyword in words for keyword in keywords):
                    return data['id']
            return self.wake_words['jarvis']['id']  # Return default pipeline ID if no keywords match
        else:
            return self.ha_pipeline  # Return the manually selected pipeline ID

    def _handle_home_assistant_error(self, error_message: str, current_message_id: int):
        self._debug_print(f"Error from Home Assistant: {error_message} (ID: {current_message_id})")
        if "Pipeline not found" in error_message:
            self._debug_print("Invalid pipeline ID. Falling back to default pipeline.")
            return self.wake_words['jarvis']['id']
        return None

    def _execute_command(self, command: str):
        self._debug_print(f"Executing command: {command}")
        if "never mind" in command.lower() or "nevermind" in command.lower():
            self._debug_print("Command contains 'never mind' or 'nevermind'. Not transmitting to assistant.")
            return
        pipeline_id = self._select_pipeline(command)
        self._send_to_home_assistant(command, pipeline_id)

    def _send_to_home_assistant(self, command, pipeline_id):
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                with self.ws_lock:
                    if not self.ws or not self.ws.connected:
                        self._debug_print(f"WebSocket not connected. Attempting to reconnect... (Attempt {attempt + 1}/{max_retries})")
                        if not self._connect_to_home_assistant():
                            if attempt == max_retries - 1:
                                self._debug_print("Failed to establish WebSocket connection after all attempts. Cannot send command.")
                                return
                            time.sleep(retry_delay)
                            continue

                    self.message_id += 1
                    current_message_id = self.message_id
                    message = {
                        "type": "assist_pipeline/run",
                        "start_stage": "intent",
                        "end_stage": "tts",
                        "input": {
                            "text": command
                        },
                        "pipeline": pipeline_id,
                        "id": current_message_id
                    }
                    self._debug_print(f"Sending command to Home Assistant: {json.dumps(message)} (ID: {current_message_id})")
                    self.ws.send(json.dumps(message))
                
                    events = []
                    timeout = 120  # Increased timeout to 120 seconds
                    start_time = time.time()
                    tts_url = None
                    tts_end_received = False
                    final_result_received = False
                    
                    while True:
                        if time.time() - start_time > timeout:
                            self._debug_print(f"Timeout waiting for response from Home Assistant (ID: {current_message_id})")
                            break

                        try:
                            response_raw = self.ws.recv()
                            self._debug_print(f"Received raw response: {response_raw}")
                            response = json.loads(response_raw)
                            self._debug_print(f"Parsed response: {json.dumps(response, indent=2)}")
                        
                            if response.get("id") != current_message_id:
                                self._debug_print(f"Received response for a different message ID: {response.get('id')}")
                                continue

                            if response.get("type") == "result":
                                if not response.get("success"):
                                    error = response.get("error", {})
                                    error_message = error.get("message", "Unknown error")
                                    new_pipeline_id = self._handle_home_assistant_error(error_message, current_message_id)
                                    if new_pipeline_id:
                                        self._debug_print(f"Retrying with new pipeline ID: {new_pipeline_id}")
                                        return self._send_to_home_assistant(command, new_pipeline_id)
                                    break
                                final_result_received = True

                            elif response.get("type") == "event":
                                events.append(response)
                                event_data = response.get("event", {}).get("data", {})
                                event_type = response.get("event", {}).get("type")
                                
                                if event_type == "tts-end":
                                    tts_output = event_data.get("tts_output", {})
                                    tts_url = tts_output.get("url")
                                    if tts_url:
                                        self._debug_print(f"Found TTS URL: {tts_url}")
                                    tts_end_received = True
                                
                                elif event_type == "voice_assistant_command":
                                    command_data = event_data
                                    command = command_data.get("command")
                                    args = command_data.get("args")
                                    self.handle_home_assistant_command(command, args)

                            if tts_url and tts_end_received and final_result_received:
                                self._debug_print("Received TTS URL, TTS end event, and final result. Processing complete.")
                                if events:
                                    self._process_events(current_message_id, events)
                                full_tts_url = f"{self.ha_url}{tts_url}"
                                self._play_audio_on_kitchen_speaker(full_tts_url)
                                return  # Successfully processed the command

                        except websocket.WebSocketException as e:
                            self._debug_print(f"WebSocket error while receiving: {str(e)}")
                            break

            except websocket.WebSocketException as e:
                self._debug_print(f"WebSocket error: {str(e)}")
            except json.JSONDecodeError:
                self._debug_print("Received invalid JSON response from Home Assistant")
            except Exception as e:
                self._debug_print(f"Error sending command to Home Assistant: {str(e)}")

            self._debug_print(f"Attempting to reconnect... (Attempt {attempt + 1}/{max_retries})")
            self._reconnect_to_home_assistant()

            if attempt < max_retries - 1:
                self._debug_print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                self._debug_print("Failed to send command after all retry attempts")

    def _play_audio_on_kitchen_speaker(self, tts_url):
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                if not self._check_websocket_connection():
                    self._debug_print("WebSocket not connected. Attempting to reconnect...")
                    if not self._reconnect_to_home_assistant():
                        raise Exception("Failed to reconnect to Home Assistant")

                # Play a short silence before the actual audio
                self.message_id += 1
                silence_url = f"{self.ha_url}/local/silence.mp3"
                silence_call = {
                    "type": "call_service",
                    "domain": "media_player",
                    "service": "play_media",
                    "service_data": {
                        "entity_id": "media_player.kitchen_display",
                        "media_content_id": silence_url,
                        "media_content_type": "music"
                    },
                    "id": self.message_id
                }
                self._debug_print(f"Sending play silence command: {json.dumps(silence_call)}")
                self._send_websocket_message(silence_call)

                # Play the actual audio immediately after silence
                self.message_id += 1
                service_call = {
                    "type": "call_service",
                    "domain": "media_player",
                    "service": "play_media",
                    "service_data": {
                        "entity_id": "media_player.kitchen_display",
                        "media_content_id": tts_url,
                        "media_content_type": "music"
                    },
                    "id": self.message_id
                }
                self._debug_print(f"Sending play audio command: {json.dumps(service_call)}")
                self._send_websocket_message(service_call)

                self._debug_print("Audio commands sent successfully")
                return

            except Exception as e:
                self._debug_print(f"Error playing audio on kitchen speaker (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    self._debug_print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)

        self._debug_print("Failed to play audio after all retry attempts")

    def _process_events(self, response_id, events):
        for event in events:
            event_type = event.get("event", {}).get("type")
            event_data = event.get("event", {}).get("data", {})
            
            if event_type == "intent_start":
                self._debug_print(f"Intent processing started (ID: {response_id})")
            elif event_type == "intent_end":
                self._debug_print(f"Intent processing ended (ID: {response_id})")
            elif event_type == "tts_start":
                self._debug_print(f"TTS processing started (ID: {response_id})")
            elif event_type == "tts_end":
                self._debug_print(f"TTS processing ended (ID: {response_id})")
                if "tts_output" in event_data:
                    self._debug_print(f"TTS output: {event_data['tts_output']}")
            else:
                self._debug_print(f"Unhandled event type: {event_type} (ID: {response_id})")

    def _connect_to_home_assistant(self):
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            with self.ws_lock:
                try:
                    ws_protocol = "wss://" if self.ha_url.startswith("https://") else "ws://"
                    ws_url = f"{ws_protocol}{self.ha_url.split('://', 1)[1]}/api/websocket"
                    self._debug_print(f"Attempting to connect to Home Assistant at {ws_url} (Attempt {attempt + 1}/{max_retries})")
                    self.ws = websocket.create_connection(ws_url, timeout=10)
                    
                    # Wait for auth_required message
                    auth_required = json.loads(self.ws.recv())
                    if auth_required.get("type") != "auth_required":
                        self._debug_print(f"Unexpected initial message: {auth_required}")
                        continue

                    auth_message = {
                        "type": "auth",
                        "access_token": self.ha_token
                    }
                    self._debug_print(f"Sending authentication message: {json.dumps(auth_message)}")
                    self.ws.send(json.dumps(auth_message))
                    
                    auth_result = json.loads(self.ws.recv())
                    if auth_result.get("type") == "auth_ok":
                        self._debug_print("Successfully connected and authenticated with Home Assistant")
                        self._subscribe_to_events()
                        return True
                    elif auth_result.get("type") == "auth_invalid":
                        self._debug_print("Authentication failed: Invalid access token")
                    else:
                        self._debug_print(f"Unexpected authentication response: {auth_result}")
                except websocket.WebSocketTimeoutException:
                    self._debug_print("Connection to Home Assistant timed out")
                except websocket.WebSocketConnectionClosedException:
                    self._debug_print("WebSocket connection to Home Assistant was closed unexpectedly")
                except json.JSONDecodeError:
                    self._debug_print("Received invalid JSON response from Home Assistant")
                except Exception as e:
                    self._debug_print(f"Failed to connect to Home Assistant: {str(e)}")
                
                if attempt < max_retries - 1:
                    self._debug_print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        
        self._debug_print("Failed to connect to Home Assistant after all retry attempts")
        return False

    def _subscribe_to_events(self):
        self.message_id += 1
        subscribe_message = {
            "id": self.message_id,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }
        self._debug_print(f"Sending subscribe message: {json.dumps(subscribe_message)}")
        self.ws.send(json.dumps(subscribe_message))
        self._debug_print(f"Subscribed to state_changed events (ID: {self.message_id})")

    def _play_chime(self):
        try:
            self.message_id += 1
            chime_url = f"{self.ha_url}/local/chime.mp3"  # Adjust this URL to the actual location of your chime sound file
            service_call = {
                "type": "call_service",
                "domain": "media_player",
                "service": "play_media",
                "service_data": {
                    "entity_id": "media_player.kitchen_display",
                    "media_content_id": chime_url,
                    "media_content_type": "music"
                },
                "id": self.message_id
            }
            self._debug_print(f"Sending play chime command: {json.dumps(service_call)}")
            with self.ws_lock:
                self.ws.send(json.dumps(service_call))

            # Wait for the response with a timeout
            timeout = 5  # 5 seconds timeout
            self.ws.settimeout(timeout)
            try:
                response_raw = self.ws.recv()
                response = json.loads(response_raw)
                self._debug_print(f"Play chime response: {json.dumps(response, indent=2)}")

                if response.get("type") == "result":
                    if response.get("success"):
                        self._debug_print("Chime played successfully")
                    else:
                        error = response.get('error', {})
                        error_message = error.get('message', 'Unknown error')
                        self._debug_print(f"Failed to play chime: {error_message}")
                else:
                    self._debug_print(f"Unexpected response type: {response.get('type')}")
            except websocket.WebSocketTimeoutException:
                self._debug_print(f"Timeout waiting for play chime response after {timeout} seconds")

        except Exception as e:
            self._debug_print(f"Error playing chime: {str(e)}")

    def _debug_print(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        print(formatted_message)
        debug_signals.debug_signal.emit(formatted_message)

    def type_string(self, text):
        """
        Types the given string using pyautogui after a 5-second delay.
        This method can be called from Home Assistant.
        """
        self._debug_print(f"Preparing to type string: {text}")
        try:
            self._debug_print("Waiting for 5 seconds before typing...")
            time.sleep(5)
            self._debug_print(f"Typing string: {text}")
            pyautogui.write(text, interval=0.05)  # Add a small delay between characters
            self._debug_print("String typed successfully")
        except Exception as e:
            self._debug_print(f"Error typing string: {str(e)}")

    def handle_home_assistant_command(self, command, args):
        """
        Handles commands received from Home Assistant.
        """
        if command == "type_string":
            if args and isinstance(args, str):
                self.type_string(args)
            else:
                self._debug_print("Invalid arguments for type_string command")
        else:
            self._debug_print(f"Unknown command: {command}")
    def _check_websocket_connection(self):
        try:
            self.ws.ping()
            return True
        except:
            return False

    def _send_websocket_message(self, message):
        try:
            self.ws.send(json.dumps(message))
            timeout = 10  # 10 seconds timeout
            self.ws.settimeout(timeout)
            response_raw = self.ws.recv()
            response = json.loads(response_raw)
            self._debug_print(f"WebSocket response: {json.dumps(response, indent=2)}")

            if response.get("type") == "result":
                if response.get("success"):
                    self._debug_print("Command executed successfully")
                else:
                    error = response.get('error', {})
                    error_message = error.get('message', 'Unknown error')
                    raise Exception(f"Failed to execute command: {error_message}")
            else:
                self._debug_print(f"Unexpected response type: {response.get('type')}")

        except websocket.WebSocketTimeoutException:
            raise Exception(f"Timeout waiting for WebSocket response after {timeout} seconds")
        except Exception as e:
            raise Exception(f"Error sending WebSocket message: {str(e)}")
