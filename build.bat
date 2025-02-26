@echo off
REM Clean up previous build artifacts
rmdir /S /Q build
rmdir /S /Q dist
del /Q *.spec

echo Building the executable...
pyinstaller --onefile --windowed elevenlabs_batch_converter.py

echo Build complete! Press any key to exit.
pause
