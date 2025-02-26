# ElevenLabs Batch Converter - Executable Guide

This guide explains how to use the standalone executable version of the ElevenLabs Batch Converter.

## Running the Executable

1. Extract all files from the zip archive (if provided in a zip)
2. Double-click the `ElevenLabs_Batch_Converter.exe` file
3. The application will start without requiring Python to be installed

## First-Time Setup

1. When you first run the application, you'll need to enter your ElevenLabs API key
2. Click "Connect" to verify your API key and load available voices
3. You can click "Save Key" to store your API key for future use

## Using the Application

1. Click "Add Files" to select audio files for conversion
2. Choose an ElevenLabs voice model from the dropdown
3. Adjust conversion settings as needed:
   - Speaker Boost: Enhances the target speaker's voice
   - Remove Background Noise: Attempts to clean up background noise
   - Stability: Controls consistency of voice generation
   - Similarity Boost: Controls how closely output matches voice samples
   - Style: Controls style exaggeration of the voice
4. Click "Start Conversion" to begin the batch process
5. Converted files will be saved in an "output" folder with the prefix "converted\_"
6. You can click "Open Output Folder" to view the converted files

## Troubleshooting

If you encounter any issues:

1. **API Key Issues**: Make sure your ElevenLabs API key is valid and has sufficient credits
2. **File Format Issues**: The application works best with common audio formats (MP3, WAV, etc.)
3. **Conversion Failures**: Check the application log for specific error messages
4. **Application Won't Start**: Make sure you have extracted all files from the zip archive

## Notes

- The executable is self-contained and doesn't require Python to be installed
- First run may take a moment as it initializes
- Your API key will be saved in the same directory as the executable if you use the "Save Key" option
- The output folder will be created in the same directory as the executable
