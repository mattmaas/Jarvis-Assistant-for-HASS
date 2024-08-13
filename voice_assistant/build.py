import PyInstaller.__main__
import os
import sys
import multiprocessing

def build_executable():
    try:
        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Define the path to the main script
        main_script = os.path.join(current_dir, 'main.py')

        # Define the path to the icon file
        icon_file = os.path.join(current_dir, 'icon.ico')

        # Define build and dist directories
        build_dir = os.path.join(current_dir, "build")
        dist_dir = os.path.join(current_dir, "dist")

        # Run PyInstaller
        PyInstaller.__main__.run([
            main_script,
            '--name=JarvisAssistant',
            '--onefile',
            '--windowed',
            f'--add-data={icon_file};.',
            '--icon=' + icon_file,
            '--hidden-import=pvporcupine',
            '--hidden-import=pyaudio',
            '--hidden-import=speech_recognition',
            '--collect-all=pvporcupine',
            '--collect-all=pyaudio',
            '--collect-all=jaraco.text',
            f'--workpath={build_dir}',
            f'--distpath={dist_dir}',
            '--clean',
            '--log-level=WARN',
            '--noconfirm',
            '--noupx',
            '--strip',
        ])
        print("Executable built successfully.")
    except Exception as e:
        print(f"Error building executable: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()
