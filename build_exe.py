import PyInstaller.__main__
import os
import sys
import shutil
from pathlib import Path

# Clean previous build artifacts if they exist
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

# Create output directory if it doesn't exist
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

# Run PyInstaller with the spec file
PyInstaller.__main__.run(['elevenlabs_batch_converter.spec', '--clean'])

print("Build completed! Executable is in the 'dist' folder.") 