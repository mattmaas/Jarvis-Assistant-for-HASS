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
import openai
from datetime import datetime
import pyautogui
from debug_window import debug_signals
from openrgb_control import OpenRGBControl
import pvporcupine
import re
import threading
class JarvisAssistant:
    def __init__(self, config_path):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.access_key = self.config['PORCUPINE']['ACCESS_KEY']
        self.sensitivity = float(self.config['PORCUPINE'].get('SENSITIVITY', '0.5'))
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
        self.rgb_control = OpenRGBControl(self.config)
        self.debug_signals = debug_signals
        self.last_ping_time = 0
        self.ping_interval = 50  # Send a ping every 50 seconds
        self.reconnect_interval = 300  # Try to reconnect every 5 minutes if disconnected
        
        # Remove Flask server initialization

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
                if keyword_index >= 0 and self.is_running:
                    self._debug_print("Wake word 'Jarvis' detected")
                    self._play_chime()
                    self.rgb_control.set_mic_color((128, 0, 128))  # Set purple color
                    self._process_speech()
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
            time.sleep(50)  # Send a ping every 50 seconds
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
                    response = json.loads(self.ws.recv())
                    if response.get("type") == "pong":
                        self._debug_print(f"Received pong (ID: {response.get('id')})")
                        return True
                    else:
                        self._debug_print(f"Unexpected response to ping: {response}")
                        return False
                except Exception as e:
                    self._debug_print(f"Error sending ping: {str(e)}")
                    if "EOF occurred in violation of protocol" in str(e):
                        self._debug_print("Critical error detected. Initiating application restart.")
                        self._restart_application()
                    return False
            return False

    def _restart_application(self):
        self._debug_print("Restarting application...")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _reconnect_to_home_assistant(self):
        max_retries = 5
        retry_delay = 60  # 1 minute between retries

        for attempt in range(max_retries):
            self._debug_print(f"Attempting to reconnect to Home Assistant (Attempt {attempt + 1}/{max_retries})")
            self._disconnect_from_home_assistant()
            
            if self._connect_to_home_assistant():
                self._debug_print("Successfully reconnected to Home Assistant")
                return True
            
            if attempt < max_retries - 1:
                self._debug_print(f"Reconnection failed. Waiting {retry_delay} seconds before next attempt...")
                time.sleep(retry_delay)

        self._debug_print("Failed to reconnect after multiple attempts. Please check your network connection and Home Assistant status.")
        return False

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
        finally:
            # Remove setting 'ice' profile here
            pass

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
            self._debug_print("Command contains 'never mind' or 'nevermind'. Not executing command.")
            self.rgb_control.set_profile("ice")  # Reset to 'ice' profile for "never mind"
            return

        self._set_processing_color()  # Set color to orange before processing

        try:
            # Load command phrases
            with open('command_phrases.json', 'r') as f:
                command_phrases = json.load(f)

            # Check for local commands
            for cmd_type, phrases in command_phrases.items():
                if any(phrase in command.lower() for phrase in phrases):
                    self._execute_local_command(cmd_type, command)
                    return

            # If no local command matched, send to Home Assistant
            pipeline_id = self._select_pipeline(command)
            self._send_to_home_assistant(command, pipeline_id)
        finally:
            if self.is_running:
                self.rgb_control.set_profile("ice")  # Reset to 'ice' profile only if still running
            else:
                self.rgb_control.set_mic_color((255, 69, 0))  # Maintain orange color if stopped

    def _execute_local_command(self, cmd_type: str, command: str):
        self._debug_print(f"Executing local command: {cmd_type}")

        if cmd_type == "stop_listening":
            self.stop()
            confirmation = "I've stopped listening"
        elif cmd_type == "start_listening":
            self.start()
            confirmation = "I've started listening"
        elif cmd_type == "type_command":
            prompt = f"Based on this input: '{command}', provide only the exact text to be typed, without any additional formatting or explanation. Remove any phrases like 'type into my pc', 'type in to my pc', 'type into pc', 'type in to pc', 'type in pc', 'type on pc', 'type for me', 'type into my computer', 'enter text', 'paste', or 'enter into my computer' from the beginning of the input. If the input suggests creating content, generate that content directly. Aim for a response of up to 1000 characters."
            extracted_info = self._query_gpt4o_mini(prompt, max_tokens=1000)
            self._type_string(extracted_info)
            confirmation = f"I've typed the text for you"
        elif cmd_type == "launch_file":
            prompt = f"Extract only the file or program name to be launched from this input: {command}"
            extracted_info = self._query_gpt4o_mini(prompt)
            self._launch_file(extracted_info)
            confirmation = f"I've launched the file or program: {extracted_info}"
        elif cmd_type == "add_file_nickname":
            prompt = f"Extract the nickname and filename from this input: {command}. Return them separated by a comma, without any additional text."
            extracted_info = self._query_gpt4o_mini(prompt)
            nickname, filename = extracted_info.split(',')
            self._add_file_nickname(nickname.strip(), filename.strip())
            confirmation = f"I've added the nickname '{nickname.strip()}' for the file '{filename.strip()}'"
        else:
            confirmation = "I'm not sure how to execute that command."

        self._send_confirmation_to_ha(confirmation)

    def _query_gpt4o_mini(self, prompt: str, max_tokens: int = 50) -> str:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                n=1,
                stop=None,
                temperature=0.5,
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            self._debug_print(f"Error querying GPT-4o-mini: {str(e)}")
            return ""

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
            "id": self.message_id
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
            self._debug_print(f"Typing string: {text}")
            pyautogui.write(text, interval=0.01)  # Reduced delay to 10 milliseconds between characters
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
