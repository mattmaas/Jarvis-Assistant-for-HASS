@echo off
echo Building Voice Assistant executable...
python build.py
if %errorlevel% neq 0 (
    echo Build failed. Please check the error messages above.
    pause
    exit /b %errorlevel%
)
echo Build completed successfully. The executable is in the 'dist' folder.
pause
