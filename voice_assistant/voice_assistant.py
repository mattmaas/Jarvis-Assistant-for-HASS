import threading
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr

class VoiceAssistant:
    def __init__(self):
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
            self.porcupine = pvporcupine.create(keywords=["jarvis"])
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
                    print("Wake word detected!")
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
            print("Listening for command...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

        try:
            command = recognizer.recognize_google(audio)
            print(f"Command recognized: {command}")
            self._execute_command(command)
        except sr.UnknownValueError:
            print("Could not understand the command")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

    def _execute_command(self, command):
        # Implement your command processing logic here
        print(f"Executing command: {command}")
        # For example:
        if "hello" in command.lower():
            print("Hello! How can I assist you?")
        elif "goodbye" in command.lower():
            print("Goodbye! Have a great day!")
        else:
            print("I'm not sure how to handle that command.")
