@echo off
echo Building Voice Assistant...

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
copy wakewords.json output\
copy file_nicknames.json output\
copy icon.png output\
copy icon.ico output\

REM Create silence.mp3 if it doesn't exist
if not exist "silence.mp3" (
    echo Creating silence.mp3...
    powershell -ExecutionPolicy Bypass -Command "$data = [byte[]]::new(44100 * 2); [System.IO.File]::WriteAllBytes('silence.mp3', $data); (Get-Item 'silence.mp3').CreationTime = Get-Date; (Get-Item 'silence.mp3').LastWriteTime = Get-Date"
)

REM Copy silence.mp3
copy silence.mp3 output\

echo Voice Assistant has been built and all necessary files have been copied to the 'output' folder.
echo You can run the executable from this folder or move it to any desired location.
pause
