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
        with sr.Microphone() as source:
            self._debug_print("Listening for command...")
            recognizer.dynamic_energy_threshold = True
            recognizer.energy_threshold = 300  # Lower value for increased sensitivity
            recognizer.pause_threshold = 0.8  # Shorter pause for faster response
            audio = recognizer.listen(source, timeout=7, phrase_time_limit=7)

        try:
            if STT_PROVIDER == "google":
                command = recognizer.recognize_google(audio, show_all=True)
                if command:
                    best_guess = command['alternative'][0]['transcript']
                    self._debug_print(f"Command recognized: {best_guess}")
                    self._execute_command(best_guess)
                else:
                    self._debug_print("Could not understand the command")
            elif STT_PROVIDER == "whisper":
                audio_data = audio.get_wav_data()
                file_obj = sr.AudioFile(io.BytesIO(audio_data))
                with file_obj as source:
                    audio_file = recognizer.record(source)
                response = openai.Audio.transcribe("whisper-1", audio_file)
                if response and 'text' in response:
                    command = response['text']
                    self._debug_print(f"Command recognized: {command}")
                    self._execute_command(command)
                else:
                    self._debug_print("Could not understand the command")
            else:
                self._debug_print("Invalid STT provider specified")
        except sr.UnknownValueError:
            self._debug_print("Could not understand the command")
        except sr.RequestError as e:
            self._debug_print(f"Could not request results; {e}")
        except Exception as e:
            self._debug_print(f"An error occurred: {e}")

    def _execute_command(self, command):
        self._debug_print(f"Executing command: {command}")
        if self.ha_pipeline:
            self._send_to_home_assistant(command)
        else:
            self._debug_print("No Home Assistant pipeline selected.")

    def _send_to_home_assistant(self, command):
        if not self.ws:
            self._connect_to_home_assistant()

        message = {
            "type": "assist_pipeline/run",
            "start_stage": "intent",
            "end_stage": "tts",
            "input": {
                "text": command
            },
            "pipeline": self.ha_pipeline
        }
        self.ws.send(json.dumps(message))
        result = json.loads(self.ws.recv())
        if result.get("success"):
            tts_url = result.get("result", {}).get("tts", {}).get("url")
            if tts_url:
                self._debug_print(f"TTS URL: {tts_url}")
            else:
                self._debug_print("No TTS URL received.")
        else:
            self._debug_print(f"Error: {result.get('error', {}).get('message', 'Unknown error')}")

    def _connect_to_home_assistant(self):
        self.ws = websocket.create_connection(f"ws://{self.ha_url}/api/websocket")
        auth_message = {
            "type": "auth",
            "access_token": self.ha_token
        }
        self.ws.send(json.dumps(auth_message))
        result = json.loads(self.ws.recv())
        if result.get("type") == "auth_ok":
            self._debug_print("Connected to Home Assistant")
        else:
            self._debug_print("Failed to connect to Home Assistant")

    def _debug_print(self, message):
        print(message)
        debug_signals.debug_signal.emit(message)
