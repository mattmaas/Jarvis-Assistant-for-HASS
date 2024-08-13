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

        # Add missing DLLs
        conda_path = os.path.dirname(sys.executable)
        openblas_dll = os.path.join(conda_path, 'Library', 'bin', 'libopenblas64__v0.3.23-293-gc2f4bdbb-gcc_10_3_0-2bde3a66a51006b2b53eb373ff767a3f.dll')
        tbb_dll = os.path.join(conda_path, 'Library', 'bin', 'tbb12.dll')

        # Run PyInstaller
        PyInstaller.__main__.run([
            f'--add-data={openblas_dll};.',
            f'--add-data={tbb_dll};.',
            main_script,
            '--name=JarvisAssistant',
            '--onefile',
            '--windowed',
            f'--add-data={icon_file};.',
            '--icon=' + icon_file,
            '--hidden-import=pvporcupine',
            '--hidden-import=pyaudio',
            '--hidden-import=speech_recognition',
            '--hidden-import=numpy',
            '--hidden-import=torch',
            '--hidden-import=numba',
            '--hidden-import=importlib_resources',
            '--hidden-import=pkg_resources',
            '--hidden-import=sip',
            '--collect-all=pvporcupine',
            '--collect-all=pyaudio',
            '--collect-all=jaraco.text',
            '--collect-all=numpy',
            '--collect-all=torch',
            '--collect-all=numba',
            f'--workpath={build_dir}',
            f'--distpath={dist_dir}',
            '--clean',
            '--log-level=DEBUG',
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
