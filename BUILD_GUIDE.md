# Building and Distributing the ElevenLabs Batch Converter

This guide explains how to build the ElevenLabs Batch Converter as a standalone executable and prepare it for distribution.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Windows, macOS, or Linux operating system

## Building the Executable

### Windows

1. Make sure you have Python installed and added to your PATH
2. Double-click the `build.bat` file
3. Wait for the build process to complete
4. The executable will be created in the `dist` folder

### macOS/Linux

1. Open a terminal in the project directory
2. Make the build script executable:
   ```
   chmod +x build.sh
   ```
3. Run the build script:
   ```
   ./build.sh
   ```
4. The executable will be created in the `dist` folder

### Manual Build (Any Platform)

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Run the build script:
   ```
   python build_exe.py
   ```
3. The executable will be created in the `dist` folder

## Packaging for Distribution

### Windows

1. After building the executable, double-click the `package.bat` file
2. A zip file will be created in the project directory with a timestamp in the filename
3. This zip file contains everything needed to run the application

### Manual Packaging (Any Platform)

1. After building the executable, run:
   ```
   python package_for_distribution.py
   ```
2. A zip file will be created in the project directory with a timestamp in the filename

## What's Included in the Distribution Package

The distribution package includes:

- `ElevenLabs_Batch_Converter.exe` - The standalone executable
- `EXECUTABLE_GUIDE.md` - Instructions for users on how to use the executable
- `README.md` - General information about the application
- `output/` - An empty directory where converted files will be saved

## Customizing the Build

If you want to customize the build process:

1. Edit the `elevenlabs_batch_converter.spec` file to change PyInstaller settings
2. Edit the `package_for_distribution.py` file to change what's included in the distribution package

## Troubleshooting

### Common Build Issues

- **Missing Dependencies**: Make sure all required packages are installed with `pip install -r requirements.txt`
- **PyInstaller Errors**: Check the PyInstaller documentation for specific error messages
- **File Not Found Errors**: Make sure all paths in the build scripts are correct

### Common Distribution Issues

- **Large Executable Size**: This is normal for PyInstaller executables as they include Python and all dependencies
- **Antivirus Warnings**: Some antivirus software may flag PyInstaller executables as suspicious. This is a false positive.
- **Missing Files in Distribution**: Check the `files_to_include` list in `package_for_distribution.py`
