import PyInstaller.__main__
import os
import sys
import shutil

def build_executable():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path to the main script
    main_script = os.path.join(current_dir, 'main.py')
    
    # Define the path to the icon file
    icon_file = os.path.join(current_dir, 'icon.ico')
    
    # Define build and dist directories
    build_dir = os.path.join(current_dir, "build")
    dist_dir = os.path.join(current_dir, "dist")
    
    # Remove existing build and dist directories
    for dir_name in [build_dir, dist_dir]:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # Add missing DLLs
    conda_path = os.path.dirname(sys.executable)
    openblas_dll = os.path.join(conda_path, 'Library', 'bin', 'libopenblas64__v0.3.23-293-gc2f4bdbb-gcc_10_3_0-2bde3a66a51006b2b53eb373ff767a3f.dll')
    tbb_dll = os.path.join(conda_path, 'Library', 'bin', 'tbb12.dll')
    api_ms_win_crt_heap_dll = os.path.join(conda_path, 'Library', 'bin', 'api-ms-win-crt-heap-l1-1-0.dll')

    dll_args = []
    for dll in [openblas_dll, tbb_dll, api_ms_win_crt_heap_dll]:
        if os.path.exists(dll):
            dll_args.append(f'--add-data={dll};.')
        else:
            print(f"Warning: {dll} not found. This may cause issues.")

    # Create the PyInstaller command
    pyinstaller_args = [
        main_script,
        '--name=JarvisAssistant',
        '--onefile',
        '--windowed',
        f'--add-data={icon_file};.',
        '--icon=' + icon_file,
        '--add-data=icon.png:.',
        '--add-data=config.ini:.',
        '--add-data=wakewords.json:.',
        '--add-data=file_nicknames.json:.',
        '--hidden-import=websocket',
        '--hidden-import=pvporcupine',
        '--hidden-import=pyaudio',
        '--hidden-import=speech_recognition',
        '--hidden-import=openai',
        '--hidden-import=requests',
        '--hidden-import=pyautogui',
        '--hidden-import=openrgb_control',
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
    ]
    
    # Run PyInstaller
    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("Executable built successfully.")
    except Exception as e:
        print(f"Error building executable: {e}")
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    build_executable()
