import threading
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
from debug_window import debug_signals

class VoiceAssistant:
    def __init__(self, access_key):
        self.access_key = access_key
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self._run).start()

    def stop(self):
        self.is_running = False

    def _run(self):
        try:
            self.porcupine = pvporcupine.create(access_key=self.access_key, keywords=["jarvis"])
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
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

        try:
            command = recognizer.recognize_google(audio)
            self._debug_print(f"Command recognized: {command}")
            self._execute_command(command)
        except sr.UnknownValueError:
            self._debug_print("Could not understand the command")
        except sr.RequestError as e:
            self._debug_print(f"Could not request results; {e}")

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
