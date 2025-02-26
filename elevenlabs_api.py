import os
import requests
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

class ElevenLabsAPI:
    """A class to interact with the ElevenLabs API for voice conversion."""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(self, api_key=None):
        """Initialize the API with a key from environment or parameter."""
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required. Set it in .env file or pass to constructor.")
        
        self.headers = {
            "xi-api-key": self.api_key,
            "accept": "application/json"
        }
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("ElevenLabsAPI")
    
    def get_voices(self):
        """Get all available voices from the API."""
        try:
            url = f"{self.BASE_URL}/voices"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching voices: {e}")
            return {"voices": []}
    
    def convert_speech_to_speech(self, voice_id, audio_file_path, output_format="mp3_44100_128"):
        """
        Convert speech in an audio file to speech with a different voice.
        
        Args:
            voice_id (str): The ID of the target voice to use
            audio_file_path (str): Path to the audio file to convert
            output_format (str): Desired output format
            
        Returns:
            bytes: The converted audio data if successful, None otherwise
        """
        try:
            url = f"{self.BASE_URL}/speech-to-speech/{voice_id}"
            
            # Speech-to-Speech endpoint payload
            files = {
                "audio": open(audio_file_path, "rb")
            }
            
            data = {
                "model_id": "eleven_multilingual_sts_v2",  # Use the Speech-to-Speech model
                "output_format": output_format
            }
            
            # Need to remove the accept header for binary response
            headers = self.headers.copy()
            headers["accept"] = "audio/mpeg"
            
            self.logger.info(f"Converting file: {audio_file_path}")
            response = requests.post(url, headers=headers, data=data, files=files)
            
            # Close the file
            files["audio"].close()
            
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error converting speech: {e}")
            if response.content:
                self.logger.error(f"Error details: {response.content.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None
            
    def get_voice_options(self):
        """Get a list of voices with their IDs and names for display in UI."""
        voices_data = self.get_voices()
        options = []
        
        if voices_data and "voices" in voices_data:
            for voice in voices_data["voices"]:
                options.append({
                    "id": voice["voice_id"],
                    "name": voice["name"],
                    "description": voice.get("description", ""),
                })
                
        return options

# Testing code
if __name__ == "__main__":
    api = ElevenLabsAPI()
    voices = api.get_voice_options()
    print(f"Found {len(voices)} voices:")
    for voice in voices[:5]:  # Show first 5 voices
        print(f"ID: {voice['id']}, Name: {voice['name']}") 