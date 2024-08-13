from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType
import time

class OpenRGBControl:
    def __init__(self):
        self.client = None
        self.mic = None
        self.connected = False

    def connect(self):
        max_retries = 3
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                self.client = OpenRGBClient(timeout=10)  # Increase timeout to 10 seconds
                devices = self.client.get_devices_by_type(DeviceType.MICROPHONE)
                if devices:
                    self.mic = devices[0]
                    self.connected = True
                    print("Connected to HyperX Quadcast S microphone")
                    return
                else:
                    print("HyperX Quadcast S microphone not found")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed to connect to HyperX Quadcast S microphone: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Max retries reached. Failed to connect to HyperX Quadcast S microphone.")
        self.connected = False

    def set_profile(self, profile_name):
        if profile_name == "ice":
            self.set_mic_gradient((0, 0, 139), (173, 216, 230))  # Dark blue to light blue
        elif profile_name == "red":
            self.set_mic_gradient((255, 0, 0), (128, 0, 128))  # Red to purple
        else:
            print(f"Profile '{profile_name}' is not supported")

    def set_mic_color(self, color):
        if not self.connected:
            self.connect()
        if self.connected and self.mic:
            try:
                self.mic.set_color(RGBColor(color[0], color[1], color[2]))
                print(f"Set microphone color to {color}")
            except Exception as e:
                print(f"Failed to set microphone color: {e}")

    def set_mic_gradient(self, top_color, bottom_color):
        if not self.connected:
            self.connect()
        if self.connected and self.mic:
            try:
                led_count = len(self.mic.leds)
                for i, led in enumerate(self.mic.leds):
                    ratio = i / (led_count - 1)
                    color = self.interpolate_color(top_color, bottom_color, ratio)
                    led.set_color(RGBColor(color[0], color[1], color[2]))
                self.mic.show()
                print(f"Set microphone gradient from {top_color} to {bottom_color}")
            except Exception as e:
                print(f"Failed to set microphone gradient: {e}")

    @staticmethod
    def interpolate_color(color1, color2, ratio):
        return tuple(int(color1[i] + (color2[i] - color1[i]) * ratio) for i in range(3))

    def close(self):
        if self.client:
            self.client.disconnect()
            print("Disconnected from HyperX Quadcast S microphone")
