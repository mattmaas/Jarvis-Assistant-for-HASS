# Jarvis Voice Assistant

This project is a voice-controlled assistant that integrates with Home Assistant and OpenRGB for smart home control and RGB lighting effects.

## Features

- Voice activation using wake word "Jarvis"
- Integration with Home Assistant for smart home control
- OpenRGB integration for controlling RGB lighting
- Configurable speech-to-text provider (Google or Whisper)
- Customizable audio feedback

## Prerequisites

- Python 3.7+
- Home Assistant instance
- OpenRGB (optional, for RGB lighting control)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy `config.ini.example` to `config.ini` and fill in your configuration details:
   ```
   cp config.ini.example config.ini
   ```

4. Edit `config.ini` with your specific settings (API keys, URLs, etc.)

## Usage

Run the assistant:

```
python main.py
```

The assistant will start and listen for the wake word "Jarvis". Once activated, you can give voice commands to control your smart home or perform other configured actions.

## Configuration

Edit the `config.ini` file to customize the assistant's behavior:

- `PORCUPINE`: Settings for the wake word detection
- `STT`: Speech-to-text provider settings
- `OPENAI`: OpenAI API settings for natural language processing
- `HOME_ASSISTANT`: Home Assistant connection details
- `OPENRGB`: OpenRGB settings for RGB lighting control
- `AUDIO`: Audio feedback settings

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
