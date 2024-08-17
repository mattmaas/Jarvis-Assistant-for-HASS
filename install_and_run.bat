@echo off
echo Installing required packages and running Voice Assistant...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python and try again.
    pause
    exit /b 1
)

REM Install required packages
echo Installing required packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Failed to install required packages. Please check the error messages above.
    pause
    exit /b %errorlevel%
)

echo Running Voice Assistant...

REM Run the main script
python main.py

pause
