@echo off
echo Running Voice Assistant (No Installation)...

REM Set the PYTHONPATH to include the current directory
set PYTHONPATH=%PYTHONPATH%;%CD%

REM Run the main script
python main.py

pause
