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

    def start(self):
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self._run).start()

    def stop(self):
        self.is_running = False

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
        try:
            if not self.ws or not self.ws.connected:
                self._debug_print("WebSocket not connected. Attempting to reconnect...")
                self._connect_to_home_assistant()

            if not self.ws or not self.ws.connected:
                self._debug_print("Failed to establish WebSocket connection. Cannot send command.")
                return

            message = {
                "type": "assist_pipeline/run",
                "start_stage": "intent",
                "end_stage": "tts",
                "input": {
                    "text": command
                },
                "pipeline": self.ha_pipeline,
                "id": 1  # Add a unique ID for the message
            }
            self._debug_print(f"Sending command to Home Assistant: {command}")
            self.ws.send(json.dumps(message))
            
            while True:
                response = json.loads(self.ws.recv())
                if response.get("type") == "result" and response.get("id") == 1:
                    if response.get("success"):
                        tts_url = response.get("result", {}).get("tts", {}).get("url")
                        if tts_url:
                            self._debug_print(f"TTS URL received: {tts_url}")
                        else:
                            self._debug_print("No TTS URL received in the response.")
                    else:
                        error_message = response.get('error', {}).get('message', 'Unknown error')
                        self._debug_print(f"Error from Home Assistant: {error_message}")
                    break
                elif response.get("type") == "event":
                    self._debug_print(f"Received event: {response}")
                else:
                    self._debug_print(f"Unexpected response: {response}")
        except websocket.WebSocketException as e:
            self._debug_print(f"WebSocket error: {str(e)}")
        except json.JSONDecodeError:
            self._debug_print("Received invalid JSON response from Home Assistant")
        except Exception as e:
            self._debug_print(f"Error sending command to Home Assistant: {str(e)}")

    def _connect_to_home_assistant(self):
        try:
            ws_protocol = "wss://" if self.ha_url.startswith("https://") else "ws://"
            ws_url = f"{ws_protocol}{self.ha_url.split('://', 1)[1]}/api/websocket"
            self._debug_print(f"Attempting to connect to Home Assistant at {ws_url}")
            self.ws = websocket.create_connection(ws_url, timeout=10)
            
            # Wait for auth_required message
            auth_required = json.loads(self.ws.recv())
            if auth_required.get("type") != "auth_required":
                self._debug_print(f"Unexpected initial message: {auth_required}")
                return

            auth_message = {
                "type": "auth",
                "access_token": self.ha_token
            }
            self._debug_print("Sending authentication message")
            self.ws.send(json.dumps(auth_message))
            
            auth_result = json.loads(self.ws.recv())
            if auth_result.get("type") == "auth_ok":
                self._debug_print("Successfully connected and authenticated with Home Assistant")
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

    def _debug_print(self, message):
        print(message)
        debug_signals.debug_signal.emit(message)
