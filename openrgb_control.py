import time
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType

class OpenRGBControl:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.device = None
        self.enabled = self.config['OPENRGB'].getboolean('ENABLED', True)
        self.device_type = getattr(DeviceType, self.config['OPENRGB'].get('DEVICE_TYPE', 'MICROPHONE'))
        if self.enabled:
            self.init_rgb_control()

    def init_rgb_control(self):
        max_retries = 3
        retry_delay = 60  # seconds

        for attempt in range(max_retries):
            try:
                self.client = OpenRGBClient()
                self.device = self.client.get_devices_by_type(self.device_type)[0]
                print("RGB control initialized successfully")
                return
            except Exception as e:
                print(f"Error initializing RGB control (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Failed to initialize RGB control after all attempts")

    def set_profile(self, profile_name):
        if not self.enabled:
            print("RGB control is disabled")
            return

        if not self.client:
            print("RGB client not initialized, attempting to reconnect...")
            self.init_rgb_control()

        if not self.client:
            print("RGB client still not initialized after retry")
            return

        try:
            self.client.load_profile(profile_name)
            print(f"Set RGB profile to {profile_name}")
        except Exception as e:
            print(f"Error setting RGB profile: {str(e)}")
            print("Attempting to reconnect and retry...")
            self.init_rgb_control()
            if self.client:
                try:
                    self.client.load_profile(profile_name)
                    print(f"Successfully set RGB profile to {profile_name} after reconnection")
                except Exception as e:
                    print(f"Error setting RGB profile after reconnection: {str(e)}")

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
