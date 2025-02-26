import os
import shutil
import subprocess
import sys

def clean_previous_builds():
    """Remove previous build artifacts"""
    print("Cleaning previous build artifacts...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # Remove any .spec files
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)

def install_requirements():
    """Ensure all requirements are installed"""
    print("Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Install PyInstaller if not already installed
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_application():
    """Build the application using PyInstaller"""
    print("Building application...")
    
    # PyInstaller command with options
    cmd = [
        "pyinstaller",
        "--name=ElevenLabsBatchConverter",
        "--onefile",  # Create a single executable
        "--windowed",  # Don't show console window (for GUI apps)
        "--add-data=README.md;.",  # Include README
        "--exclude-module=.env",  # Exclude .env file
        "--noconfirm",  # Overwrite output directory without asking
        "--hidden-import=PyQt6.sip",  # Add explicit import for sip
        "elevenlabs_batch_converter.py"  # Main script
    ]
    
    # Add icon if available
    # if os.path.exists("icon.ico"):
    #     cmd.insert(2, "--icon=icon.ico")
    
    subprocess.check_call(cmd)
    
    # Create output directory in the dist folder
    dist_output = os.path.join("dist", "output")
    if not os.path.exists(dist_output):
        os.makedirs(dist_output)

def main():
    """Main build process"""
    print("Starting build process...")
    
    # Clean previous builds
    clean_previous_builds()
    
    # Install requirements
    install_requirements()
    
    # Build the application
    build_application()
    
    print("\nBuild completed successfully!")
    print("The executable can be found in the 'dist' folder.")

if __name__ == "__main__":
    main() 