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
from debug_window import debug_signals

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
        self.ha_pipeline = None
        self.ws = None
        self.message_id = 0  # Initialize message ID counter
        self.ws_lock = threading.Lock()  # Add a lock for thread-safe WebSocket operations

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._connect_to_home_assistant()  # Connect to Home Assistant when starting
            threading.Thread(target=self._run).start()
            threading.Thread(target=self._keep_alive).start()  # Start keep-alive thread

    def stop(self):
        self.is_running = False
        self._disconnect_from_home_assistant()

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
                    self._debug_print("Wake word detected!")
                    self._process_speech()

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
                        audio_data = audio.get_raw_data()
                        response = openai.Audio.transcribe("whisper-1", audio_data, model="whisper-1")
                        if response and 'text' in response:
                            command = response['text']
                            self._debug_print(f"Command recognized: {command}")
                            self._execute_command(command)
                        else:
                            self._debug_print("Could not understand the command")
                    except Exception as e:
                        self._debug_print(f"Error in Whisper transcription: {e}")
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
        if self.ha_pipeline:
            self._send_to_home_assistant(command)
        else:
            self._debug_print("No Home Assistant pipeline selected.")

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
                self._debug_print(f"Sending command to Home Assistant: {command} (ID: {current_message_id})")
                self.ws.send(json.dumps(message))
                
                tts_url = None
                response_speech = None
                events = []
                timeout = 30  # Set a timeout of 30 seconds
                start_time = time.time()
                
                while True:
                    if time.time() - start_time > timeout:
                        self._debug_print(f"Timeout waiting for response from Home Assistant (ID: {current_message_id})")
                        break

                    response = json.loads(self.ws.recv())
                    self._debug_print(f"Received response: {response}")
                    
                    if isinstance(response, dict):
                        if response.get("id") == current_message_id:
                            if response.get("type") == "event":
                                events.append(response)
                            elif response.get("type") == "result":
                                if response.get("success"):
                                    self._debug_print(f"Command processed successfully (ID: {current_message_id})")
                                else:
                                    error = response.get('error', {})
                                    if isinstance(error, dict):
                                        error_message = error.get('message', 'Unknown error')
                                        self._debug_print(f"Error from Home Assistant: {error_message} (ID: {current_message_id})")
                                    else:
                                        self._debug_print(f"Unexpected 'error' structure in response: {error} (ID: {current_message_id})")
                                break
                        else:
                            self._debug_print(f"Received response for different ID: {response.get('id')}")
                    else:
                        self._debug_print(f"Unexpected response structure: {response}")
                
                # Process events after receiving the final result
                for event in events:
                    event_data = event.get("event", {})
                    event_type = event_data.get("type")
                    if event_type == "tts-end":
                        tts_data = event_data.get("data", {}).get("tts_output", {})
                        tts_url = tts_data.get("url")
                        if tts_url:
                            self._debug_print(f"TTS URL received: {tts_url} (ID: {current_message_id})")
                        else:
                            self._debug_print(f"No TTS URL received in the tts-end event (ID: {current_message_id})")
                    elif event_type == "intent-end":
                        intent_output = event_data.get("data", {}).get("intent_output", {})
                        response_speech = intent_output.get("response", {}).get("speech", {}).get("plain", {}).get("speech")
                        if response_speech:
                            self._debug_print(f"Response from Home Assistant: {response_speech} (ID: {current_message_id})")
                
                if tts_url:
                    self._play_audio_on_google_home(tts_url)
                elif response_speech:
                    self._debug_print(f"No TTS URL, but text response received: {response_speech} (ID: {current_message_id})")
                else:
                    self._debug_print(f"No TTS URL or text response received. This might indicate an issue with the Home Assistant pipeline or TTS service (ID: {current_message_id})")
            except websocket.WebSocketException as e:
                self._debug_print(f"WebSocket error: {str(e)}")
                self._reconnect_to_home_assistant()
            except json.JSONDecodeError:
                self._debug_print("Received invalid JSON response from Home Assistant")
            except Exception as e:
                self._debug_print(f"Error sending command to Home Assistant: {str(e)}")
                self._reconnect_to_home_assistant()

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
                self._debug_print("Sending authentication message")
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
        self.ws.send(json.dumps(subscribe_message))
        self._debug_print(f"Subscribed to state_changed events (ID: {self.message_id})")

    def _debug_print(self, message):
        print(message)
        debug_signals.debug_signal.emit(message)

    def _play_audio_on_google_home(self, tts_url):
        try:
            self.message_id += 1
            play_message = {
                "type": "call_service",
                "domain": "media_player",
                "service": "play_media",
                "target": {
                    "entity_id": "media_player.kitchen_display"
                },
                "service_data": {
                    "media_content_id": tts_url,
                    "media_content_type": "music"
                },
                "id": self.message_id
            }
            self._debug_print(f"Sending play command to Google Home: {play_message}")
            self.ws.send(json.dumps(play_message))

            # Wait for the result
            response = json.loads(self.ws.recv())
            if response.get("type") == "result" and response.get("success"):
                self._debug_print("Audio playback command sent successfully to Google Home")
            else:
                self._debug_print(f"Failed to send audio playback command: {response}")
        except Exception as e:
            self._debug_print(f"Error playing audio on Google Home: {str(e)}")
