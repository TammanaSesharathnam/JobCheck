@echo off
echo Starting JobCheck Backend...
cd /d "%~dp0JobCheck\backend"
if %errorlevel% neq 0 (
    echo Error: Could not find the backend directory.
    pause
    exit /b
)

echo Installing dependencies (if needed)...
pip install -r ..\..\requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b
)

echo Starting Flask Server...
python app.py
pause
