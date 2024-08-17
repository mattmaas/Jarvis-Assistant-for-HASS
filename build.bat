@echo off
echo Setting up environment and building Portable Voice Assistant...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python and try again.
    pause
    exit /b 1
)

REM Create and activate a virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate

REM Install required packages
echo Installing required packages...
pip install -r requirements.txt
pip install pyinstaller

REM Run the build script
echo Building the executable...
python build.py

if %errorlevel% neq 0 (
    echo Build failed. Please check the error messages above.
    pause
    exit /b %errorlevel%
)

REM Create an output directory
if not exist "output" mkdir output

REM Copy the executable
copy dist\JarvisAssistant.exe output\

REM Copy necessary files
copy config.ini output\
copy icon.png output\
copy icon.ico output\

echo Portable Voice Assistant has been built and all necessary files have been copied to the 'output' folder.
echo You can run the executable from this folder or move it to any desired location.

REM Deactivate the virtual environment
call venv\Scripts\deactivate

pause
