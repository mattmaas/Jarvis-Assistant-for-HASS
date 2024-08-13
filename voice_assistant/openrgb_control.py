from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType
import time

class OpenRGBControl:
    def __init__(self):
        self.client = None
        self.mic = None
        self.connected = False

    def connect(self):
        try:
            self.client = OpenRGBClient()
            devices = self.client.get_devices_by_type(DeviceType.MICROPHONE)
            if devices:
                self.mic = devices[0]
                self.connected = True
                print("Connected to HyperX Quadcast S microphone")
            else:
                print("HyperX Quadcast S microphone not found")
                self.connected = False
        except Exception as e:
            print(f"Failed to connect to HyperX Quadcast S microphone: {e}")
            self.connected = False

    def set_profile(self, profile_name):
        print(f"Setting profile '{profile_name}' is not supported for direct microphone control")

    def set_mic_color(self, color):
        if not self.connected:
            self.connect()
        if self.connected and self.mic:
            try:
                self.mic.set_color(RGBColor(color[0], color[1], color[2]))
                print(f"Set microphone color to {color}")
            except Exception as e:
                print(f"Failed to set microphone color: {e}")

    def close(self):
        if self.client:
            self.client.disconnect()
            print("Disconnected from HyperX Quadcast S microphone")
