@echo off
echo Building Portable Voice Assistant...

REM Run the build script
python build.py

if %errorlevel% neq 0 (
    echo Build failed. Please check the error messages above.
    pause
    exit /b %errorlevel%
)

REM Create a portable directory
mkdir portable_voice_assistant

REM Copy the executable
copy dist\JarvisAssistant.exe portable_voice_assistant\

REM Copy necessary files
copy config.ini portable_voice_assistant\
copy wakewords.json portable_voice_assistant\
copy file_nicknames.json portable_voice_assistant\
copy icon.png portable_voice_assistant\
copy icon.ico portable_voice_assistant\

echo Portable Voice Assistant has been created in the 'portable_voice_assistant' folder.
echo You can move this folder to any location and run the executable from there.
pause
