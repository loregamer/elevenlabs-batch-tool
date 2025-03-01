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

## To Do / Future Features

The following features could be added to enhance the voice changing capabilities:

### Voice Conversion Enhancements

- **Voice Seed Parameter**: Add support for the `seed` parameter to enable deterministic voice generation for consistent results when converting the same audio multiple times.
- **Voice Isolation Pre-processing**: Implement the ElevenLabs Audio Isolation API as a pre-processing step to clean up input audio before voice conversion.
- **Clarity Boost**: Add support for the clarity boost parameter available in newer ElevenLabs models.
- **Chunking for Large Files**: Implement chunking to process longer audio files in segments, improving reliability and potentially reducing processing time.
- **Pronunciation Guide**: Add support for pronunciation dictionaries to improve specific word pronunciations.

### Voice Creation and Management

- **Voice Generation from Description**: Add the ability to generate custom voices from text descriptions using the Voice Generation API.
- **Voice Cloning from Samples**: Allow users to create custom voices by uploading voice samples.
- **Voice Library Management**: Add functionality to save, categorize, and manage favorite voices.

### Advanced Processing

- **Timestamps and Word-level Control**: Implement support for generating timestamps for each word, enabling more precise audio editing.
- **Streaming Processing**: Add streaming support for real-time processing of audio files.
- **Language Detection and Translation**: Automatically detect the source language and offer translation options.
- **Batch Processing Optimization**: Implement parallel processing for multiple files to speed up batch conversions.

### User Experience

- **Audio Preview**: Add the ability to preview how a voice will sound before processing the entire file.
- **Advanced Output Settings**: Provide more control over output audio quality, format, and compression.
- **Preset Management**: Allow saving and loading of voice conversion presets.
- **Progress Estimation**: Implement more accurate progress and time remaining estimates.
