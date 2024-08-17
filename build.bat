@echo off
echo Building Portable Voice Assistant...

REM Run the build script
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
pause
