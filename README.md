# ElevenLabs Batch Voice Converter

A GUI tool for batch processing audio files using ElevenLabs' voice conversion technology.

## Features

- Upload multiple audio files for processing
- Select from available ElevenLabs voice models
- Convert audio files one by one with the selected voice
- Track conversion progress
- Save converted files to your chosen location
- Enter your API key directly in the application

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
   - You can click "Save Key" to store your API key for future use
3. Click "Add Files" to select audio files for conversion
4. Choose an ElevenLabs voice model from the dropdown
5. Click "Start Conversion" to begin the batch process
6. Converted files will be saved in an "output" folder with the prefix "converted\_"

## Important Notes

- This tool uses the ElevenLabs Speech-to-Speech API to change the voice in audio files
- Processing large files consumes more API credits
- Conversion time depends on file size and internet connection
- You can save your API key to avoid entering it every time
