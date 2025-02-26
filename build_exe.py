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

# Create an empty .env file if it doesn't exist
# This prevents PyInstaller from showing an error when looking for the file
if not os.path.exists(".env"):
    print("Creating empty .env file for build process...")
    with open(".env", "w") as f:
        f.write("# This file was automatically created during the build process\n")
        f.write("# You can add your ELEVENLABS_API_KEY here if desired\n")
        f.write("# ELEVENLABS_API_KEY=your_api_key_here\n")

# Run PyInstaller with the spec file
PyInstaller.__main__.run(['elevenlabs_batch_converter.spec', '--clean'])

print("Build completed! Executable is in the 'dist' folder.") 