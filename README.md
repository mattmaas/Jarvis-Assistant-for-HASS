# Jarvis: Your Ultimate Voice-Controlled Smart Home Assistant

Welcome to Jarvis, the cutting-edge voice assistant that revolutionizes your smart home experience. Seamlessly blending advanced AI technology with intuitive voice control, Jarvis brings your home to life like never before.

## Unleash the Power of Your Voice

Jarvis isn't just another voice assistant – it's your personal AI-powered home conductor. With the simple wake word "Jarvis," you unlock a world of possibilities:

- **Effortless Smart Home Control**: Command your entire smart home ecosystem with natural language. From adjusting lights to setting the perfect temperature, Jarvis understands and executes your wishes instantly.

- **Stunning RGB Lighting Effects**: Transform your space with vibrant, mood-enhancing lighting. Jarvis's OpenRGB integration lets you create the perfect ambiance for any occasion, all with a simple voice command.

- **AI-Powered Conversations**: Powered by OpenAI's cutting-edge language models, Jarvis engages in natural, context-aware conversations. It's not just following commands; it's understanding your intent.

- **Extensible Home Assistant Integration**: Leverage the full power of Home Assistant's vast ecosystem. Jarvis seamlessly integrates with Home Assistant's Assist pipelines, allowing for complex automations and interactions with all your smart devices.

- **Crystal-Clear Voice Feedback**: Experience responses like never before with high-quality audio feedback. Jarvis's voice is not just functional; it's a pleasure to listen to.

## Beyond Voice: Your Personal Computer Assistant

Jarvis goes beyond smart home control. It's your intelligent computer companion:

- **Effortless Typing**: Dictate emails, messages, or documents with incredible accuracy. Jarvis types for you, saving time and effort.

- **Quick File Access**: Launch applications or open files with a simple voice command. No more digging through folders – just ask Jarvis.

- **Custom Shortcuts**: Create personalized voice shortcuts for your most common computer tasks. Boost your productivity with tailored voice commands.

## Endless Possibilities with Open-Source Flexibility

Jarvis is built on an open-source foundation, making it infinitely extensible:

- **Custom Integrations**: Easily add new functionalities or integrate with your favorite services.
- **Community-Driven Development**: Benefit from a growing ecosystem of plugins and extensions.
- **Tailored to Your Needs**: Modify and adapt Jarvis to fit your unique smart home setup.

## Experience the Future of Smart Home Control

Jarvis isn't just a voice assistant; it's a gateway to a more intuitive, efficient, and enjoyable smart home experience. Say goodbye to fumbling with apps or remotes – with Jarvis, your voice is all you need to command your digital kingdom.

Ready to transform your home into an AI-powered oasis? Follow the installation guide below and step into the future of smart living!

## Installation Guide

### Prerequisites

Before installing Jarvis, ensure you have the following:

1. Python 3.7 or higher
2. Home Assistant instance set up and running
3. OpenRGB (optional, for RGB lighting control)
4. Git (for cloning the repository)

### Step-by-Step Installation

1. Clone the Jarvis repository:
   ```
   git clone https://github.com/yourusername/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Copy the example configuration file:
   ```
   cp config.ini.example config.ini
   ```

5. Edit `config.ini` with your specific settings:
   - Set your Porcupine access key
   - Configure your OpenAI API key
   - Add your Home Assistant access token and URL
   - Adjust other settings as needed

6. Run the assistant:
   ```
   python main.py
   ```

## Configuration

The `config.ini` file allows you to customize various aspects of Jarvis. Here's a detailed breakdown of each section:

### PORCUPINE
- `ACCESS_KEY`: Your Porcupine API key (string)
- `SENSITIVITY`: Wake word detection sensitivity (float between 0 and 1, e.g., 0.5)

### STT (Speech-to-Text)
- `PROVIDER`: Choose your STT provider ("google" or "whisper")

### OPENAI
- `API_KEY`: Your OpenAI API key (string)

### HOME_ASSISTANT
- `ACCESS_TOKEN`: Your Home Assistant long-lived access token (string)
- `URL`: The URL of your Home Assistant instance (e.g., "https://your-home-assistant-url.com")

### OPENRGB
- `ENABLED`: Enable or disable RGB lighting control (true or false)
- `DEVICE_TYPE`: The type of RGB device to control (e.g., "MICROPHONE", "KEYBOARD", etc.)

### AUDIO
- `CHIME_FILE`: The filename of your chime sound (e.g., "chime.mp3")
- `KITCHEN_SPEAKER`: The entity ID of your kitchen speaker in Home Assistant (e.g., "media_player.kitchen_display")

Ensure all API keys and tokens are kept secret and not shared publicly. Adjust these settings according to your specific setup and preferences.

## Auto Interpreter Mode for Voice Pipelines

Jarvis now starts in auto interpreter mode by default for voice pipelines. This intelligent feature automatically selects the most appropriate pipeline based on the content of your voice command. Here's how it works:

1. When you give a voice command, Jarvis analyzes the content of your speech.
2. Based on keywords and context, it selects the most suitable Home Assistant Assist pipeline to process your request.
3. This allows for more flexible and context-aware responses, as different pipelines can be optimized for various types of commands (e.g., smart home control, information queries, or complex tasks).

You can still manually select a specific pipeline if needed, but the auto interpreter mode ensures that Jarvis adapts to your diverse needs without requiring explicit pipeline selection for each command.

## Usage

Once Jarvis is running:

1. Say the wake word "Jarvis" to activate the assistant.
2. Give your command or ask a question.
3. Jarvis will process your request and respond accordingly.

### Example Commands

- "Jarvis, turn on the living room lights"
- "Jarvis, what's the temperature outside?"
- "Jarvis, type an email to John"
- "Jarvis, open my project folder"

## Troubleshooting

If you encounter any issues:

1. Check the console output for error messages.
2. Ensure all API keys and tokens in `config.ini` are correct.
3. Verify your Home Assistant instance is accessible.
4. For RGB control issues, check that OpenRGB is running and configured correctly.

## Contributing

We welcome contributions to Jarvis! If you have ideas for improvements or new features:

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your fork and submit a pull request

Please ensure your code adheres to the project's coding standards and include tests for new features.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

For questions, issues, or feature requests, please open an issue on the GitHub repository. We're here to help you make the most of your Jarvis experience!

Transform your home into an AI-powered marvel with Jarvis – where the future of smart living becomes your everyday reality!
