@echo off
echo Installing requirements...
pip install -r requirements.txt

echo Building portable executable...
python build.py

echo Moving executable to current directory...
move dist\VoiceAssistant.exe .

echo Done! VoiceAssistant.exe is now in the current directory.
pause
