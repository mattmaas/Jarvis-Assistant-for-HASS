import os
import sys
import configparser
import threading
import json
import time
import websocket
import pyaudio
import struct
import speech_recognition as sr
import io
from openai import OpenAI
from datetime import datetime
import pyautogui
from debug_window import debug_signals
from debug_window import debug_signals
from modern_ui import conversation_signals
from openrgb_control import OpenRGBControl
import pvporcupine
import re
import threading
import uuid
import random
import time
import logging
import threading
from websocket import WebSocketException

class JarvisAssistant:
    def __init__(self, config_path, logger):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.logger = logger
        self.request_logger = logging.getLogger('request_logger')
        self.request_logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler('api_requests.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.request_logger.addHandler(fh)
        self.access_key = self.config['PORCUPINE']['ACCESS_KEY']
        self.sensitivity = float(self.config['PORCUPINE'].get('SENSITIVITY', '0.5'))
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False
        self.debug_signals = debug_signals
        self.last_wakeword_index = -1
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.openai_client = OpenAI(api_key=self.config['OPENAI']['API_KEY'])
        self.stt_provider = self.config['STT']['PROVIDER']
        self.ha_url = self.config['HOME_ASSISTANT']['URL']
        self.ha_token = self.config['HOME_ASSISTANT']['ACCESS_TOKEN']
        self.ha_pipeline = "auto"  # Set default pipeline to auto interpreter mode
        self.ws = None
        self.message_id = 0  # Initialize message ID counter
        self.ws_lock = threading.Lock()  # Add a lock for thread-safe WebSocket operations
        self.wake_words = self._load_wake_words()
        self.rgb_control = OpenRGBControl(self.config)
        self.debug_signals = debug_signals
        self.last_ping_time = 0
        self.ping_interval = 50  # Send a ping every 50 seconds
        self.reconnect_interval = 30  # Try to reconnect every 30 seconds initially
        self.conversation_id = str(uuid.uuid4())  # Generate a unique conversation ID
        self.last_request_time = time.time()  # Initialize last request time
        self.conversation_timeout = 1200  # 20 minutes in seconds
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 15  # Increased max attempts for more retries
        self.base_reconnect_delay = 10  # Base delay of 10 seconds
        # Get the directory of the current script
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # Voice change tracking
        self.current_voice = None
        self.voice_change_time = time.time()  # Initialize with current time
        self.voice_duration = 300  # 5 minutes in seconds

        # # Blueberry long-term conversation
        # self.use_blueberry_longterm = self.config['BLUEBERRY'].getboolean('USE_LONGTERM_CONVERSATION', False)
        # self.blueberry_conversation_id = self.config['BLUEBERRY'].get('LONGTERM_CONVERSATION_ID', str(uuid.uuid4()))
        
        # Remove Flask server initialization

    def _load_wake_words(self):
        try:
            wakewords_path = os.path.join(self.script_dir, 'wakewords.json')
            with open(wakewords_path, 'r') as f:
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
        self._debug_print("Assistant started and listening")

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
        if self.is_running:
            self.is_running = False
            self._debug_print("Stopping assistant...")
            try:
                self._disconnect_from_home_assistant()
            except Exception as e:
                self._debug_print(f"Error disconnecting from Home Assistant: {str(e)}")
            
            try:
                self.rgb_control.set_mic_color((255, 69, 0))  # Set to a more vibrant orange color (Red-Orange)
                self._debug_print("Set RGB color to (255, 69, 0)")
            except Exception as e:
                self._debug_print(f"Error setting RGB color: {str(e)}")
            
            self._debug_print("Assistant stopped")
        else:
            self._debug_print("Assistant is already stopped")
        
        # Ensure the color stays orange even after stopping
        self.rgb_control.set_mic_color((255, 69, 0))

    def _run(self):
        try:
            self.porcupine = pvporcupine.create(access_key=self.access_key, keywords=["jarvis", "blueberry"], sensitivities=[self.sensitivity, self.sensitivity])
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
                
                if keyword_index >= 0 and self.is_running:
                    self.last_wakeword_index = keyword_index
                    if keyword_index == 0:
                        self._debug_print("Wake word 'Jarvis' detected")
                        self._play_chime()
                        self.rgb_control.set_mic_color((128, 0, 128))  # Set purple color
                        self._process_speech()
                    elif keyword_index == 1:
                        self._debug_print("Wake word 'Blueberry' detected")
                        self._play_chime()
                        self.rgb_control.set_mic_color((0, 0, 255))  # Set blue color
                        blueberry_pipeline_id = self.wake_words.get('blueberry', {}).get('id')
                        self._process_speech(pipeline_id=blueberry_pipeline_id)
                    # Remove setting 'ice' profile here

        finally:
            if self.audio_stream:
                self.audio_stream.close()
            if self.pa:
                self.pa.terminate()
            if self.porcupine:
                self.porcupine.delete()

    def _keep_alive(self):
        while self.is_running:
            time.sleep(self.ping_interval)
            if not self._send_ping():
                self._reconnect_to_home_assistant()

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

                    # Wait for pong response
                    self.ws.settimeout(10)  # Set a 10-second timeout for the response
                    while True:
                        response = json.loads(self.ws.recv())
                        if response.get("type") == "pong":
                            self._debug_print(f"Received pong (ID: {response.get('id')})")
                            self.reconnect_attempts = 0  # Reset reconnect attempts on successful ping
                            return True
                        elif response.get("type") == "event":
                            self._debug_print(f"Received event during ping: {response}")
                            continue
                        else:
                            self._debug_print(f"Unexpected response to ping: {response}")
                            return False
                except Exception as e:
                    self._debug_print(f"Error sending ping: {str(e)}")
                    return False
            return False

    def _restart_application(self):
        self._debug_print("Restarting application...")
        if getattr(sys, 'frozen', False):
            executable = sys.executable
        else:
            executable = sys.argv[0]
        
        self._debug_print(f"Executable path: {executable}")
        
        # Stop the current instance
        self.stop()
        
        # Start a new instance
        try:
            os.execv(executable, [executable] + sys.argv[1:])
        except Exception as e:
            self._debug_print(f"Error restarting application: {str(e)}")
            import subprocess
            subprocess.Popen([executable] + sys.argv[1:])
        
        # Exit the current instance
        sys.exit(0)

    def _handle_critical_error(self, error_message):
        self._debug_print(f"Critical error detected: {error_message}")
        self._debug_print("Initiating application restart.")
        self._restart_application()

    def _reconnect_to_home_assistant(self):
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self._debug_print("Max reconnection attempts reached. Restarting application...")
            self._restart_application()
            return False

        retry_delay = self.base_reconnect_delay * (1.5 ** (self.reconnect_attempts - 1))
        retry_delay = min(retry_delay, 300)  # Cap at 5 minutes
        jitter = random.uniform(0.8, 1.2)
        retry_delay = int(retry_delay * jitter)

        self._debug_print(f"Attempting to reconnect to Home Assistant (Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        self._disconnect_from_home_assistant()
        
        if self._connect_to_home_assistant():
            self._debug_print("Successfully reconnected to Home Assistant")
            self.reconnect_attempts = 0
            return True
        
        self._debug_print(f"Reconnection failed. Waiting {retry_delay} seconds before next attempt...")
        time.sleep(retry_delay)

        return False

    def _disconnect_from_home_assistant(self):
        with self.ws_lock:
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    self._debug_print(f"Error closing WebSocket: {str(e)}")
                finally:
                    self.ws = None

    def _process_speech(self, pipeline_id=None):
        recognizer = sr.Recognizer()
        default_pipeline = self.wake_words['jarvis']['id']
        original_pipeline = self.ha_pipeline

        try:
            with sr.Microphone() as source:
                self._debug_print("Listening for command...")
                recognizer.dynamic_energy_threshold = True
                recognizer.energy_threshold = 300  # Lower value for increased sensitivity
                recognizer.pause_threshold = 0.8  # Reduced pause threshold for quicker response
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=120)

            if self.is_running:
                self._set_processing_color()  # Set color to orange after listening

            try:
                if self.stt_provider == "google":
                    command = recognizer.recognize_google(audio, show_all=True)
                    if command:
                        best_guess = command['alternative'][0]['transcript']
                        self._debug_print(f"Command recognized: {best_guess}")
                        
                        # Set the pipeline for this command
                        if pipeline_id:
                            self._debug_print(f"Setting pipeline to {pipeline_id}")
                            self.ha_pipeline = pipeline_id
                        
                        response = self._execute_command(best_guess, self.ha_pipeline)
                        
                        # Always reset to default pipeline after command execution
                        self._debug_print(f"Resetting pipeline to default (Jarvis)")
                        self.ha_pipeline = default_pipeline
                        
                        return response
                    else:
                        self._debug_print("Could not understand the command")
                elif self.stt_provider == "whisper":
                    try:
                        audio_data = audio.get_wav_data()
                        audio_file = io.BytesIO(audio_data)
                        audio_file.name = 'audio.wav'  # Add a name attribute to the BytesIO object
                        response = self.openai_client.audio.transcriptions.create(model="whisper-1", file=audio_file)
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
        finally:
            if self.is_running:
                self.rgb_control.set_profile("ice")  # Always set back to 'ice' profile after processing
                self._debug_print("Set RGB profile back to 'ice'")

    def _select_pipeline(self, text: str) -> tuple:
        self._debug_print("def _select_pipeline(self, text: str) -> tuple")
        
        # Check for voice reversion commands
        if any(phrase in text.lower() for phrase in ["revert voice", "clear voice", "normal voice"]):
            self._debug_print("Voice reversion command detected. Reverting to default voice.")
            self.ha_pipeline = "auto"
            return self.wake_words['jarvis']['id'], True

        text_lower = text.lower()
        words = text_lower.split()

        # Always check for keywords, regardless of current ha_pipeline value
        for pipeline_name, data in self.wake_words.items():
            keywords = self.pipeline_keywords.get(pipeline_name, [])
            self._debug_print(keywords)
            if any(keyword.lower() in text_lower for keyword in keywords) or \
               any(keyword.lower() in words for keyword in keywords):
                self._debug_print(f"Keyword match: Voice changed to {data['name']}.")
                # if pipeline_name == 'blueberry' and self.use_blueberry_longterm:
                #     self._debug_print("Using Blueberry's long-term conversation ID.")
                #     self.conversation_id = self.blueberry_conversation_id
                self.ha_pipeline = data['id']
                return data['id'], True

        # If no specific voice is selected and Jarvis wake word was used, reset to auto
        if "jarvis" in text_lower or "jarvis" in words:
            self._debug_print("Jarvis wake word detected. Resetting to auto mode.")
            self.ha_pipeline = "auto"
            return self.wake_words['jarvis']['id'], False

        # If ha_pipeline is not "auto" and no keyword match, use the current pipeline
        if self.ha_pipeline != "auto":
            is_new_voice = self.ha_pipeline != self.current_voice
            return self.ha_pipeline, is_new_voice

        # Default case: use Jarvis
        self._debug_print("No specific voice selected. Using default (Jarvis).")
        return self.wake_words['jarvis']['id'], False

    def _handle_home_assistant_error(self, error_message: str, current_message_id: int):
        self._debug_print(f"Error from Home Assistant: {error_message} (ID: {current_message_id})")
        if "Pipeline not found" in error_message:
            self._debug_print("Invalid pipeline ID. Falling back to default pipeline.")
            return self.wake_words['jarvis']['id']
        return None

    def _refresh_conversation_id(self):
        current_time = time.time()
        if current_time - self.last_request_time > self.conversation_timeout:
            self.conversation_id = str(uuid.uuid4())
            self._debug_print(f"Refreshed conversation ID: {self.conversation_id}")
        self.last_request_time = current_time
        
    def _check_and_refresh_conversation_id(self):
        self._refresh_conversation_id()

    def _execute_command(self, command: str, pipeline_id: str = None):
        result = None
        try:
            self._refresh_conversation_id()
            self._debug_print(f"Executing command: {command}")
            conversation_signals.update_signal.emit(command, True)  # Update ModernUI with user's command
            if any(phrase in command.lower() for phrase in ["never mind", "nevermind", "be quiet", "shut up"]):
                self._debug_print("Command cancelled by user.")
                conversation_signals.update_signal.emit("Command cancelled.", False)  # Update ModernUI with cancellation
                return

            self._set_processing_color()  # Set color to orange before processing

            # Load command phrases
            command_phrases_path = os.path.join(self.script_dir, 'command_phrases.json')
            with open(command_phrases_path, 'r') as f:
                command_phrases = json.load(f)

            # Check for local commands
            for cmd_type, phrases in command_phrases.items():
                if any(phrase in command.lower() for phrase in phrases):
                    response = self._execute_local_command(cmd_type, command)
                    self._debug_print(f"Local command response: {response}")
                    conversation_signals.update_signal.emit(response, False)  # Update ModernUI with response
                    return

            # If no local command matched, send to Home Assistant
            if pipeline_id is None:
                pipeline_id = self._select_pipeline(command)
            response = self._send_to_home_assistant(command, pipeline_id)
            if response:
                self._debug_print(f"Home Assistant response: {response}")
                conversation_signals.update_signal.emit(response, False)  # Emit the response
                result = response
            else:
                fallback_response = self._query_gpt4o_mini(f"Respond to this user query: {command}", max_tokens=150)
                self._debug_print(f"Fallback response: {fallback_response}")
                conversation_signals.update_signal.emit(fallback_response, False)
                result = fallback_response
            
        except Exception as e:
            error_message = f"Error executing command: {str(e)}"
            self._debug_print(error_message)
            conversation_signals.update_signal.emit(error_message, False)  # Update ModernUI with error message
            result = error_message
        finally:
            self.rgb_control.set_profile("ice")  # Always reset to 'ice' profile after processing
            self._debug_print("Reset RGB profile to 'ice' after command execution")

        # Removed follow-up functionality
        
        # Debug print current voice information
        if self.current_voice:
            time_left = self.voice_duration - (time.time() - self.voice_change_time)
            self._debug_print(f"Current voice: {self.current_voice}, Time left: {int(time_left)} seconds")
        else:
            self._debug_print("Using default voice")

    def _execute_local_command(self, cmd_type: str, command: str):
        self._debug_print(f"Executing local command: {cmd_type}")

        if cmd_type == "stop_listening":
            self.stop()
            confirmation = "I've stopped listening. You can wake me up again by saying 'Hey Jarvis'."
        elif cmd_type == "start_listening":
            self.start()
            confirmation = "I'm now listening and ready to assist you."
        elif cmd_type == "type_command":
            prompt = f"Based on this input: '{command}', provide only the exact text to be typed, without any additional formatting or explanation. Remove any phrases like 'type into my pc', 'type in to my pc', 'type into pc', 'type in to pc', 'type in pc', 'type on pc', 'type for me', 'type into my computer', 'enter text', 'paste', or 'enter into my computer' from the beginning of the input. If the input suggests creating content, generate that content directly. Aim for a response of up to 1000 characters."
            extracted_info = self._query_gpt4o_mini(prompt, max_tokens=1000)
            self._type_string(extracted_info)
            confirmation = f"I've typed the following text for you: {extracted_info[:50]}..."
        elif cmd_type == "launch_file":
            prompt = f"Extract only the file or program name to be launched from this input: {command}"
            extracted_info = self._query_gpt4o_mini(prompt)
            self._launch_file(extracted_info)
            confirmation = f"I'm launching the file or program: {extracted_info}"
        elif cmd_type == "add_file_nickname":
            prompt = f"Extract the nickname and filename from this input: {command}. Return them separated by a comma, without any additional text."
            extracted_info = self._query_gpt4o_mini(prompt)
            nickname, filename = extracted_info.split(',')
            self._add_file_nickname(nickname.strip(), filename.strip())
            confirmation = f"I've added the nickname '{nickname.strip()}' for the file '{filename.strip()}'"
        elif cmd_type == "switch_conversation":
            confirmation = self._switch_conversation_id()
        else:
            confirmation = "I'm not sure how to execute that command."

        self._send_confirmation_to_ha(confirmation)
        self._narrate_action(confirmation)
        return confirmation

    def _narrate_action(self, message):
        try:
            self.message_id += 1
            service_call = {
                "id": self.message_id,
                "type": "call_service",
                "domain": "tts",
                "service": "google_translate_say",
                "service_data": {
                    "entity_id": "media_player.kitchen_display",
                    "message": message
                }
            }
            self._debug_print(f"Sending narration command: {json.dumps(service_call)}")
            self._send_websocket_message(service_call)
        except Exception as e:
            self._debug_print(f"Error narrating action: {str(e)}")

    def _query_gpt4o_mini(self, prompt: str, max_tokens: int = 50) -> str:
        try:
            functions = [
                {
                    "name": "process_user_input",
                    "description": "Process the user's input and generate an appropriate response",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "response": {
                                "type": "string",
                                "description": "The generated response to the user's input"
                            },
                            "expects_reply": {
                                "type": "boolean",
                                "description": "Whether the response expects a reply from the user"
                            }
                        },
                        "required": ["response", "expects_reply"]
                    }
                }
            ]

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                functions=functions,
                function_call={"name": "process_user_input"},
                max_tokens=max_tokens,
                n=1,
                stop=None,
                temperature=0.5,
                user=self.conversation_id
            )

            function_call = response.choices[0].message.function_call
            if function_call and function_call.name == "process_user_input":
                function_args = json.loads(function_call.arguments)
                return function_args.get("response", ""), function_args.get("expects_reply", False)
            else:
                return response.choices[0].message.content.strip(), False

        except Exception as e:
            self._debug_print(f"Error querying GPT-4o-mini: {str(e)}")
            return "", False

    def _send_confirmation_to_ha(self, confirmation: str):
        if not self.is_running:
            self._debug_print("Assistant is stopped. Skipping confirmation to Home Assistant.")
            return

        pipeline_id = self._select_pipeline("confirmation")
        message = {
            "type": "assist_pipeline/run",
            "start_stage": "tts",
            "end_stage": "tts",
            "input": {
                "text": confirmation
            },
            "pipeline": pipeline_id,
            "conversation_id": self.message_id
        }
        try:
            self._send_websocket_message(message)
        except Exception as e:
            self._debug_print(f"Error sending confirmation to Home Assistant: {str(e)}")
            if "NoneType" in str(e):
                self._debug_print("WebSocket connection is not available. Attempting to reconnect...")
                if self._reconnect_to_home_assistant():
                    self._debug_print("Reconnected successfully. Retrying confirmation...")
                    try:
                        self._send_websocket_message(message)
                    except Exception as retry_e:
                        self._debug_print(f"Failed to send confirmation after reconnection: {str(retry_e)}")
                else:
                    self._debug_print("Failed to reconnect to Home Assistant.")

    def _launch_file(self, filename: str):
        try:
            os.startfile(filename)
            self._debug_print(f"Launched file: {filename}")
        except Exception as e:
            self._debug_print(f"Error launching file: {str(e)}")

    def _add_file_nickname(self, nickname: str, filename: str):
        try:
            with open('file_nicknames.json', 'r+') as f:
                nicknames = json.load(f)
                nicknames[nickname] = filename
                f.seek(0)
                json.dump(nicknames, f, indent=2)
            self._debug_print(f"Added nickname '{nickname}' for file '{filename}'")
        except Exception as e:
            self._debug_print(f"Error adding file nickname: {str(e)}")

    def _switch_conversation_id(self):
        self.conversation_id = str(uuid.uuid4())
        self._debug_print(f"Switched to new conversation ID: {self.conversation_id}")
        confirmation = "Conversation cleared. Starting a new conversation."
        self._send_confirmation_to_ha(confirmation)
        self._send_message_to_kitchen_display(confirmation)
        self._play_tts_message(confirmation)
        return confirmation

    def _play_tts_message(self, message):
        try:
            self.message_id += 1
            service_call = {
                "id": self.message_id,
                "type": "call_service",
                "domain": "tts",
                "service": "google_translate_say",
                "target": {
                    "entity_id": "media_player.kitchen_display"
                },
                "service_data": {
                    "message": message
                }
            }
            self._debug_print(f"Sending TTS message: {json.dumps(service_call)}")
            self._send_websocket_message(service_call)
        except Exception as e:
            self._debug_print(f"Error playing TTS message: {str(e)}")

    def _send_message_to_kitchen_display(self, message):
        try:
            self.message_id += 1
            service_call = {
                "id": self.message_id,
                "type": "call_service",
                "domain": "notify",
                "service": "kitchen_display",
                "service_data": {
                    "message": message
                }
            }
            self._debug_print(f"Sending message to kitchen display: {json.dumps(service_call)}")
            self._send_websocket_message(service_call)
        except Exception as e:
            self._debug_print(f"Error sending message to kitchen display: {str(e)}")

    def _send_to_home_assistant(self, command, pipeline_id):
        max_retries = 3
        retry_delay = 5  # seconds
        overall_timeout = 900  # seconds (15 minutes) - keeping this value

        pipeline_id, is_new_voice = self._select_pipeline(command)
        current_time = time.time()
        
        if is_new_voice or (self.voice_change_time and current_time - self.voice_change_time > self.voice_duration):
            self.conversation_id = str(uuid.uuid4())
            self._debug_print(f"New conversation ID generated: {self.conversation_id}")
            self.voice_change_time = current_time
        elif current_time - self.last_request_time > self.conversation_timeout:
            self.conversation_id = str(uuid.uuid4())
            self._debug_print(f"Conversation timed out. New conversation ID generated: {self.conversation_id}")
        
        self.last_request_time = current_time
        self.current_voice = pipeline_id

        start_time = time.time()
        while time.time() - start_time < overall_timeout:
            try:
                with self.ws_lock:
                    if not self.ws or not self.ws.connected:
                        self._debug_print("WebSocket not connected. Attempting to reconnect...")
                        if not self._connect_to_home_assistant():
                            raise Exception("Failed to establish WebSocket connection")

                    self.message_id += 1
                    current_message_id = self.message_id
                    message = {
                        "id": current_message_id,
                        "type": "assist_pipeline/run",
                        "start_stage": "intent",
                        "end_stage": "tts",
                        "input": {
                            "text": command
                        },
                        "pipeline": pipeline_id,
                        "conversation_id": self.conversation_id
                    }
                    self._debug_print(f"Sending command to Home Assistant: {json.dumps(message)} (ID: {current_message_id})")
                    self.request_logger.debug(f"Raw request to Home Assistant: {json.dumps(message)}")
                    self.ws.send(json.dumps(message))
                
                events = []
                tts_url = None
                tts_end_received = False
                final_result_received = False
                response_text = ""
                
                initial_period = 100  # First 100 seconds
                while time.time() - start_time < overall_timeout:
                    elapsed_time = time.time() - start_time
                    check_interval = 20 if elapsed_time <= initial_period else 30  # 20s for first 100s, then 30s
                    try:
                        self.ws.settimeout(check_interval)  # Set timeout to check interval
                        response_raw = self.ws.recv()
                        self._debug_print(f"Received raw response: {response_raw}")
                        response = json.loads(response_raw)
                        self._debug_print(f"Parsed response: {json.dumps(response, indent=2)}")
                    
                        if response.get("id") != current_message_id:
                            self._debug_print(f"Received response for a different message ID: {response.get('id')}")
                            continue

                        if response.get("type") == "event":
                            events.append(response)
                            event_data = response.get("event", {}).get("data", {})
                            event_type = response.get("event", {}).get("type")
                            
                            if event_type == "intent-end":
                                speech = event_data.get("intent_output", {}).get("response", {}).get("speech", {}).get("plain", {}).get("speech")
                                if speech:
                                    self._debug_print(f"Extracted speech from intent-end: {speech}")
                                    response_text = speech
                                    conversation_signals.update_signal.emit(command, True)  # Emit user's command
                                    conversation_signals.update_signal.emit(response_text, False)  # Emit Jarvis's response
                                    self._debug_print(f"User command: {command}")
                                    self._debug_print(f"Jarvis response: {response_text}")
                            
                            elif event_type == "tts-end":
                                tts_output = event_data.get("tts_output", {})
                                tts_url = tts_output.get("url")
                                if tts_url:
                                    self._debug_print(f"Found TTS URL: {tts_url}")
                                    full_tts_url = f"{self.ha_url}{tts_url}"
                                    self._debug_print(f"Playing audio on kitchen speaker: {full_tts_url}")
                                    self._play_audio_on_kitchen_speaker(full_tts_url)
                                tts_end_received = True
                            
                            elif event_type == "run-end":
                                final_result_received = True

                            elif event_type == "error":
                                error_message = event_data.get("message", "Unknown error")
                                self._debug_print(f"Error event received: {error_message}")
                                return f"Error from Home Assistant: {error_message}"

                        elif response.get("type") == "result":
                            if not response.get("success"):
                                error = response.get("error", {})
                                error_message = error.get("message", "Unknown error")
                                self._debug_print(f"Error result received: {error_message}")
                                return f"Error from Home Assistant: {error_message}"
                            final_result_received = True

                        if response_text and tts_end_received and final_result_received:
                            self._debug_print("Received response text, TTS end event, and final result. Processing complete.")
                            if events:
                                self._process_events(current_message_id, events)
                            
                            return response_text

                    except websocket.WebSocketTimeoutException:
                        self._debug_print("Timeout while waiting for response, continuing to next iteration")
                        continue
                    except websocket.WebSocketException as e:
                        self._debug_print(f"WebSocket error while receiving: {str(e)}")
                        break

                self._debug_print("Timeout reached while processing response")
                return "Timeout waiting for complete response from Home Assistant. Please try again."

            except Exception as e:
                self._debug_print(f"Error in communication with Home Assistant: {str(e)}")
                if time.time() - start_time + retry_delay < overall_timeout:
                    self._debug_print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    break

        return "Failed to get a complete response from Home Assistant after multiple attempts. Please try again later."

    def _play_audio_on_kitchen_speaker(self, tts_url):
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                if not self._check_websocket_connection():
                    self._debug_print("WebSocket not connected. Attempting to reconnect...")
                    if not self._reconnect_to_home_assistant():
                        raise Exception("Failed to reconnect to Home Assistant")

                self.message_id += 1
                service_call = {
                    "id": self.message_id,
                    "type": "call_service",
                    "domain": "media_player",
                    "service": "play_media",
                    "target": {
                        "entity_id": "media_player.kitchen_display"
                    },
                    "service_data": {
                        "media_content_id": tts_url,
                        "media_content_type": "music"
                    }
                }
                self._debug_print(f"Sending play audio command: {json.dumps(service_call)}")
                self.request_logger.debug(f"Raw request to play audio: {json.dumps(service_call)}")
                self._send_websocket_message(service_call)

                self._debug_print("Audio command sent successfully")
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
            
            if event_type == "run-start":
                self._debug_print(f"Run started (ID: {response_id})")
            elif event_type == "intent-start":
                self._debug_print(f"Intent processing started (ID: {response_id})")
            elif event_type == "intent-end":
                self._debug_print(f"Intent processing ended (ID: {response_id})")
                speech = event_data.get("intent_output", {}).get("response", {}).get("speech", {}).get("plain", {}).get("speech")
                if speech:
                    self._debug_print(f"Speech from intent-end: {speech}")
            elif event_type == "tts-start":
                self._debug_print(f"TTS processing started (ID: {response_id})")
            elif event_type == "tts-end":
                self._debug_print(f"TTS processing ended (ID: {response_id})")
                if "tts_output" in event_data:
                    self._debug_print(f"TTS output: {event_data['tts_output']}")
            elif event_type == "run-end":
                self._debug_print(f"Run ended (ID: {response_id})")
            else:
                self._debug_print(f"Unhandled event type: {event_type} (ID: {response_id})")

    def _connect_to_home_assistant(self):
        with self.ws_lock:
            try:
                ws_protocol = "wss://" if self.ha_url.startswith("https://") else "ws://"
                ws_url = f"{ws_protocol}{self.ha_url.split('://', 1)[1]}/api/websocket"
                self._debug_print(f"Attempting to connect to Home Assistant at {ws_url}")
                self.ws = websocket.create_connection(ws_url, timeout=300)  # 5-minute connection timeout
                
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
            chime_file = self.config['AUDIO'].get('CHIME_FILE', 'chime.mp3')
            chime_url = f"{self.ha_url}/local/{chime_file}"
            kitchen_speaker = self.config['AUDIO'].get('KITCHEN_SPEAKER', 'media_player.kitchen_display')
            service_call = {
                "type": "call_service",
                "domain": "media_player",
                "service": "play_media",
                "service_data": {
                    "entity_id": kitchen_speaker,
                    "media_content_id": chime_url,
                    "media_content_type": "music"
                },
                "id": self.message_id
            }
            self._debug_print(f"Sending play chime command: {json.dumps(service_call)}")
            self.request_logger.debug(f"Raw request to play chime: {json.dumps(service_call)}")
            with self.ws_lock:
                self.ws.send(json.dumps(service_call))

            # Wait for the response with a timeout
            timeout = 300  # 5-minute timeout
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
        self.logger.debug(message)
        formatted_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {message}"
        print(formatted_message)
        self.debug_signals.debug_signal.emit(formatted_message)

    def _set_processing_color(self):
        try:
            self.rgb_control.set_mic_color((255, 69, 0))  # Set to orange color
            self._debug_print("Set RGB color to orange (processing)")
        except Exception as e:
            self._debug_print(f"Error setting RGB color to orange: {str(e)}")

    def _type_string(self, text):
        """
        Types the given string using pyautogui.
        """
        self._debug_print(f"Preparing to type string: {text}")
        try:
            if isinstance(text, tuple):
                text = text[0]  # Use the first element of the tuple
            text = str(text)  # Convert to string to handle non-string inputs
            self._debug_print(f"Typing string: {text}")
            pyautogui.write(text, interval=0.05)  # Set delay to 50 milliseconds between characters
            self._debug_print("String typed successfully")
        except Exception as e:
            self._debug_print(f"Error typing string: {str(e)}")
    def _check_websocket_connection(self):
        try:
            self.ws.ping()
            return True
        except:
            return False

    def _send_websocket_message(self, message):
        try:
            self.ws.send(json.dumps(message))
            timeout = 300  # 5-minute timeout
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


