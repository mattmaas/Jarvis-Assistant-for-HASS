import threading
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import openai
from debug_window import debug_signals
from config import STT_PROVIDER, OPENAI_API_KEY

class VoiceAssistant:
    def __init__(self, access_key, sensitivity=0.5):
        self.access_key = access_key
        self.sensitivity = sensitivity
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False
        openai.api_key = OPENAI_API_KEY

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
        # Implement your command processing logic here
        self._debug_print(f"Executing command: {command}")
        # For example:
        if "hello" in command.lower():
            self._debug_print("Hello! How can I assist you?")
        elif "goodbye" in command.lower():
            self._debug_print("Goodbye! Have a great day!")
        else:
            self._debug_print("I'm not sure how to handle that command.")

    def _debug_print(self, message):
        print(message)
        debug_signals.debug_signal.emit(message)
