from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType

class OpenRGBControl:
    def __init__(self):
        self.client = None
        self.device = None
        self.init_rgb_control()

    def init_rgb_control(self):
        try:
            self.client = OpenRGBClient()
            self.device = self.client.get_devices_by_type(DeviceType.MICROPHONE)[0]
            print("RGB control initialized successfully")
        except Exception as e:
            print(f"Error initializing RGB control: {str(e)}")

    def set_profile(self, profile_name):
        if not self.device:
            print("RGB device not initialized")
            return

        profile_map = {
            "ice": RGBColor(173, 216, 230),  # Light blue
            "red": RGBColor(255, 0, 0),
        }

        color = profile_map.get(profile_name.lower())
        if color:
            try:
                self.device.set_color(color)
                print(f"Set RGB profile to {profile_name}")
            except Exception as e:
                print(f"Error setting RGB profile: {str(e)}")
        else:
            print(f"Unknown profile: {profile_name}")

    def set_mic_color(self, color):
        if not self.device:
            print("RGB device not initialized")
            return

        try:
            self.device.set_color(RGBColor(*color))
            print(f"Set RGB color to {color}")
        except Exception as e:
            print(f"Error setting RGB color: {str(e)}")

    def close(self):
        if self.client:
            self.client.disconnect()
            print("RGB control disconnected")
