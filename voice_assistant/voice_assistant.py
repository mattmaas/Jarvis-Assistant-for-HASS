import threading
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import openai
import io
import configparser
import websocket
import json
import time
import requests
from debug_window import debug_signals
from datetime import datetime
from openrgb_control import OpenRGBControl

class VoiceAssistant:
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

    def _load_wake_words(self):
        return {"jarvis": {"id": "jarvis_en", "name": "Jarvis"}}

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._connect_to_home_assistant()  # Connect to Home Assistant when starting
            self.rgb_control.set_profile("ice")  # Set OpenRGB profile to 'ice'
            threading.Thread(target=self._run).start()
            threading.Thread(target=self._keep_alive).start()  # Start keep-alive thread

    def stop(self):
        self.is_running = False
        self._disconnect_from_home_assistant()
        self.rgb_control.set_profile("red")  # Set OpenRGB profile to 'red'
        self.rgb_control.close()

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
                    self.rgb_control.set_profile("ice")  # Reset to 'ice' profile after processing

        finally:
            if self.audio_stream:
                self.audio_stream.close()
            if self.pa:
                self.pa.terminate()
            if self.porcupine:
                self.porcupine.delete()

    def _keep_alive(self):
        while self.is_running:
            time.sleep(50)  # Send a ping every 50 seconds
            self._send_ping()

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
        self._connect_to_home_assistant()

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
                recognizer.pause_threshold = 0.8  # Shorter pause for faster response
                audio = recognizer.listen(source, timeout=7, phrase_time_limit=7)

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

    def _execute_command(self, command):
        self._debug_print(f"Executing command: {command}")
        self._send_to_home_assistant(command)

    def _send_to_home_assistant(self, command):
        with self.ws_lock:
            try:
                if not self.ws or not self.ws.connected:
                    self._debug_print("WebSocket not connected. Attempting to reconnect...")
                    if not self._connect_to_home_assistant():
                        self._debug_print("Failed to establish WebSocket connection. Cannot send command.")
                        return

                self.message_id += 1
                current_message_id = self.message_id
                message = {
                    "type": "assist_pipeline/run",
                    "start_stage": "intent",
                    "end_stage": "tts",
                    "input": {
                        "text": command
                    },
                    "pipeline": self.ha_pipeline,
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

                    response_raw = self.ws.recv()
                    self._debug_print(f"Received raw response: {response_raw}")
                    response = json.loads(response_raw)
                    self._debug_print(f"Parsed response: {json.dumps(response, indent=2)}")
                    
                    if isinstance(response, dict):
                        response_id = response.get("id")
                        response_type = response.get("type")
                        
                        if response_id == current_message_id:
                            if response_type == "event":
                                events.append(response)
                                self._debug_print(f"Received event: {json.dumps(response, indent=2)}")
                                
                                event_data = response.get("event", {}).get("data", {})
                                event_type = response.get("event", {}).get("type")
                                
                                if event_type == "tts-end":
                                    tts_output = event_data.get("tts_output", {})
                                    tts_url = tts_output.get("url")
                                    if tts_url:
                                        self._debug_print(f"Found TTS URL: {tts_url}")
                                    tts_end_received = True
                                    self._debug_print("TTS end event received")
                            
                            elif response_type == "result":
                                final_result_received = True
                                if response.get("success"):
                                    self._debug_print(f"Command processed successfully (ID: {response_id})")
                                else:
                                    error = response.get('error', {})
                                    if isinstance(error, dict):
                                        error_message = error.get('message', 'Unknown error')
                                        self._debug_print(f"Error from Home Assistant: {error_message} (ID: {response_id})")
                                    else:
                                        self._debug_print(f"Unexpected 'error' structure in response: {error} (ID: {response_id})")
                                self._debug_print(f"Final result: {json.dumps(response, indent=2)}")
                        else:
                            self._debug_print(f"Received response for a different message ID: {response_id}")
                    else:
                        self._debug_print(f"Unexpected response structure: {response}")
                    
                    # Check if we have received all necessary components
                    if tts_url and tts_end_received and final_result_received:
                        self._debug_print("Received TTS URL, TTS end event, and final result. Processing complete.")
                        if events:
                            self._process_events(current_message_id, events)
                        full_tts_url = f"{self.ha_url}{tts_url}"
                        self._play_audio_on_kitchen_speaker(full_tts_url)
                        break
                                     # Handle incoming commands from Home Assistant
                    if response_type == "event" and response.get("event", {}).get("type") == "voice_assistant_command":
                        command_data = response.get("event", {}).get("data", {})
                        command = command_data.get("command")
                        args = command_data.get("args")
                        self.handle_home_assistant_command(command, args)

            except websocket.WebSocketException as e:
                self._debug_print(f"WebSocket error: {str(e)}")
                self._reconnect_to_home_assistant()
            except json.JSONDecodeError:
                self._debug_print("Received invalid JSON response from Home Assistant")
            except Exception as e:
                self._debug_print(f"Error sending command to Home Assistant: {str(e)}")
                self._reconnect_to_home_assistant()

    def _play_audio_on_kitchen_speaker(self, tts_url):
        try:
            # Construct the service call to play audio on the kitchen speaker
            self.message_id += 1
            service_call = {
                "type": "call_service",
                "domain": "media_player",
                "service": "play_media",
                "service_data": {
                    "entity_id": "media_player.kitchen_display",  # Updated kitchen speaker entity ID
                    "media_content_id": tts_url,
                    "media_content_type": "music"
                },
                "id": self.message_id
            }
            self._debug_print(f"Sending play audio command: {json.dumps(service_call)}")
            self.ws.send(json.dumps(service_call))

            # Wait for the response with a timeout
            timeout = 10  # 10 seconds timeout
            self.ws.settimeout(timeout)
            try:
                response_raw = self.ws.recv()
                response = json.loads(response_raw)
                self._debug_print(f"Play audio response: {json.dumps(response, indent=2)}")

                if response.get("type") == "result":
                    if response.get("success"):
                        self._debug_print("Audio playing on kitchen speaker")
                    else:
                        error = response.get('error', {})
                        error_message = error.get('message', 'Unknown error')
                        self._debug_print(f"Failed to play audio: {error_message}")
                else:
                    self._debug_print(f"Unexpected response type: {response.get('type')}")
            except websocket.WebSocketTimeoutException:
                self._debug_print(f"Timeout waiting for play audio response after {timeout} seconds")

        except websocket.WebSocketException as e:
            self._debug_print(f"WebSocket error while playing audio: {str(e)}")
        except json.JSONDecodeError as e:
            self._debug_print(f"Error decoding JSON response: {str(e)}")
        except Exception as e:
            self._debug_print(f"Unexpected error playing audio on kitchen speaker: {str(e)}")

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
        with self.ws_lock:
            try:
                ws_protocol = "wss://" if self.ha_url.startswith("https://") else "ws://"
                ws_url = f"{ws_protocol}{self.ha_url.split('://', 1)[1]}/api/websocket"
                self._debug_print(f"Attempting to connect to Home Assistant at {ws_url}")
                self.ws = websocket.create_connection(ws_url, timeout=10)
                
                # Wait for auth_required message
                auth_required = json.loads(self.ws.recv())
                if auth_required.get("type") != "auth_required":
                    self._debug_print(f"Unexpected initial message: {auth_required}")
                    return False

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
        Types the given string using pyautogui.
        This method can be called from Home Assistant.
        """
        self._debug_print(f"Typing string: {text}")
        try:
            pyautogui.typewrite(text)
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