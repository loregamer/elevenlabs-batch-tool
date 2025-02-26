import os
import requests
import logging
import json

class ElevenLabsAPI:
    """A class to interact with the ElevenLabs API for voice conversion."""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(self, api_key=None):
        """Initialize the API with a key from parameter."""
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required. Pass it to the constructor.")
        
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
    
    def get_remaining_credits(self):
        """
        Get the remaining credits in the user's subscription.
        
        Returns:
            dict: A dictionary containing subscription information including remaining credits
                  or None if the request fails
        """
        try:
            url = f"{self.BASE_URL}/user/subscription"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            subscription_data = response.json()
            
            # Extract the relevant credit information
            credits_info = {
                "character_count": subscription_data.get("character_count", 0),
                "character_limit": subscription_data.get("character_limit", 0),
                "remaining_characters": 0,
                "tier": subscription_data.get("tier", ""),
                "next_character_count_reset_unix": subscription_data.get("next_character_count_reset_unix", 0)
            }
            
            # Calculate remaining characters
            if "character_count" in subscription_data and "character_limit" in subscription_data:
                credits_info["remaining_characters"] = subscription_data["character_limit"] - subscription_data["character_count"]
            
            self.logger.info(f"Remaining credits: {credits_info['remaining_characters']} characters")
            return credits_info
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching subscription info: {e}")
            if 'response' in locals() and response.content:
                self.logger.error(f"Error details: {response.content.decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching subscription info: {e}")
            return None
    
    def convert_speech_to_speech(self, voice_id, audio_file_path, model_id="eleven_multilingual_sts_v2", 
                                speaker_boost=True, remove_background_noise=False, output_format="mp3_44100_128",
                                stability=0.5, similarity_boost=0.75, style=0.0):
        """
        Convert speech in an audio file to speech with a different voice.
        
        Args:
            voice_id (str): The ID of the target voice to use
            audio_file_path (str): Path to the audio file to convert
            model_id (str): The model to use for conversion. Options:
                           "eleven_multilingual_sts_v2" (default) - Multilingual model
                           "eleven_english_sts_v2" - English-only model
            speaker_boost (bool): Whether to enhance the target speaker's voice (default: True)
            remove_background_noise (bool): Whether to remove background noise (default: False)
            output_format (str): Desired output format
            stability (float): Value between 0 and 1 that affects the consistency of voice generation (default: 0.5)
            similarity_boost (float): Value between 0 and 1 that affects how closely the output matches the voice samples (default: 0.75)
            style (float): Value between 0 and 1 that affects the style exaggeration of the voice (default: 0.0)
            
        Returns:
            bytes: The converted audio data if successful, None otherwise
        """
        try:
            url = f"{self.BASE_URL}/speech-to-speech/{voice_id}"
            
            # Speech-to-Speech endpoint payload
            files = {
                "audio": open(audio_file_path, "rb")
            }
            
            # According to ElevenLabs API, the parameter is called "remove_silence"
            data = {
                "model_id": model_id,
                "output_format": output_format,
                "speaker_boost": speaker_boost,
                "remove_silence": remove_background_noise  # API parameter name is different from our method parameter
            }
            
            # Add voice settings if provided
            voice_settings = {}
            if stability is not None:
                voice_settings["stability"] = stability
            if similarity_boost is not None:
                voice_settings["similarity_boost"] = similarity_boost
            if style is not None:
                voice_settings["style"] = style
                
            # Only add voice_settings to data if it's not empty
            # Convert voice_settings to a JSON string as required by the API
            if voice_settings:
                data["voice_settings"] = json.dumps(voice_settings)
            
            # Need to remove the accept header for binary response
            headers = self.headers.copy()
            headers["accept"] = "audio/mpeg"
            
            self.logger.info(f"Converting file: {audio_file_path} with model: {model_id}, speaker_boost: {speaker_boost}, remove_silence: {remove_background_noise}")
            self.logger.info(f"Voice settings: stability={stability}, similarity_boost={similarity_boost}, style={style}")
            response = requests.post(url, headers=headers, data=data, files=files)
            
            # Close the file
            files["audio"].close()
            
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error converting speech: {e}")
            if 'response' in locals() and response.content:
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
    
    def get_model_options(self):
        """Get a list of available models for speech-to-speech conversion."""
        return [
            {
                "id": "eleven_multilingual_sts_v2",
                "name": "Eleven Multilingual v2",
                "description": "Supports multiple languages"
            },
            {
                "id": "eleven_english_sts_v2",
                "name": "Eleven English v2",
                "description": "Optimized for English language"
            }
        ]

# Testing code
if __name__ == "__main__":
    api = ElevenLabsAPI()
    
    # Test getting remaining credits
    credits = api.get_remaining_credits()
    if credits:
        print(f"Subscription tier: {credits['tier']}")
        print(f"Character limit: {credits['character_limit']}")
        print(f"Used characters: {credits['character_count']}")
        print(f"Remaining characters: {credits['remaining_characters']}")
    
    # Test getting voices
    voices = api.get_voice_options()
    print(f"\nFound {len(voices)} voices:")
    for voice in voices[:5]:  # Show first 5 voices
        print(f"ID: {voice['id']}, Name: {voice['name']}")
    
    # Test getting models
    models = api.get_model_options()
    print(f"\nAvailable models:")
    for model in models:
        print(f"ID: {model['id']}, Name: {model['name']}") 