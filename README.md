# ElevenLabs Batch Voice Converter

A GUI tool for batch processing audio files using ElevenLabs' voice conversion technology.

## Features

- Upload multiple audio files for processing
- Select from available ElevenLabs voice models
- Convert audio files one by one with the selected voice
- Track conversion progress
- Save converted files to your chosen location
- Enter your API key directly in the application
- Securely store your API key in your system's credential manager

## Requirements

- Python 3.8+
- ElevenLabs API key (you can get one from [ElevenLabs](https://elevenlabs.io/))

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python elevenlabs_batch_converter.py
   ```
2. Enter your ElevenLabs API key and click "Connect"
   - You can click "Save Key" to securely store your API key in your system's credential manager
3. Click "Add Files" to select audio files for conversion
4. Choose an ElevenLabs voice model from the dropdown
5. Click "Start Conversion" to begin the batch process
6. Converted files will be saved in an "output" folder with the prefix "converted\_"

## Important Notes

- This tool uses the ElevenLabs Speech-to-Speech API to change the voice in audio files
- Processing large files consumes more API credits
- Conversion time depends on file size and internet connection
- Your API key is securely stored in your system's credential manager (Windows Credential Manager, macOS Keychain, or Linux Secret Service)

## If Python randomly breaks

`pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip pyqt6-tools`
`pip install PyQt6==6.6.1 PyQt6-Qt6==6.6.1 PyQt6-sip`
