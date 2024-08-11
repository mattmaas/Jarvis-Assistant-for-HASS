@echo off
echo Installing requirements...
pip install -r requirements.txt

echo Installing PyAudio...
pip install --upgrade setuptools
pip install --upgrade wheel
pip install pyaudio

echo Running the Voice Assistant...
python main.py

pause
