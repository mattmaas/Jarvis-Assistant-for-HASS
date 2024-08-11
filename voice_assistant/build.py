import PyInstaller.__main__
import os

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the path to the main script
main_script = os.path.join(current_dir, 'main.py')

# Define the path to the icon file
icon_file = os.path.join(current_dir, 'icon.ico')

# Run PyInstaller
PyInstaller.__main__.run([
    main_script,
    '--name=VoiceAssistant',
    '--onefile',
    '--windowed',
    f'--add-data={icon_file};.',
    '--icon=' + icon_file,
    '--hidden-import=pvporcupine',
    '--hidden-import=pyaudio',
    '--hidden-import=speech_recognition',
    '--collect-all=pvporcupine',
])
