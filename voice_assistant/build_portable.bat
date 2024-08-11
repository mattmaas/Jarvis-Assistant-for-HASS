@echo off
echo Installing requirements...
pip install -r requirements.txt

echo Installing PyAudio...
pip install --upgrade setuptools
pip install --upgrade wheel
pip install pyaudio

echo Building portable executable...
python build.py

if exist dist\VoiceAssistant.exe (
    echo Moving executable to current directory...
    move dist\VoiceAssistant.exe .
    echo Done! VoiceAssistant.exe is now in the current directory.
) else (
    echo Error: VoiceAssistant.exe was not created. Check the build output for errors.
)

pause
