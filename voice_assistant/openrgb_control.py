import openrgb
from openrgb.utils import RGBColor, DeviceType
import time

class OpenRGBControl:
    def __init__(self):
        self.client = None
        self.mic = None
        self.connected = False

    def connect(self):
        try:
            self.client = openrgb.OpenRGBClient()
            devices = self.client.get_devices_by_type(DeviceType.MICROPHONE)
            if devices:
                self.mic = devices[0]
                self.connected = True
                print("Connected to OpenRGB")
            else:
                print("No microphone device found in OpenRGB")
                self.connected = False
        except openrgb.OpenRGBClientError as e:
            print(f"Failed to connect to OpenRGB: {e}")
            self.connected = False
        except Exception as e:
            print(f"Unexpected error connecting to OpenRGB: {e}")
            self.connected = False

    def set_profile(self, profile_name):
        if not self.connected:
            self.connect()
        if self.connected:
            try:
                self.client.load_profile(profile_name)
                print(f"Set OpenRGB profile to {profile_name}")
            except Exception as e:
                print(f"Failed to set OpenRGB profile: {e}")

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
            print("Disconnected from OpenRGB")
