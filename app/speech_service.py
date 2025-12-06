"""
Google Cloud Speech-to-Text and Text-to-Speech Service
Supports voice input/output for the chatbot in multiple languages (en-IN, hi-IN, bn-IN)
"""

import os
import io
import logging
from typing import Optional, Tuple
from pathlib import Path

from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as texttospeech
from google.oauth2 import service_account
import base64

from app.config import get_settings

logger = logging.getLogger(__name__)

# Language code mappings
LANGUAGE_CODES = {
    'en': 'en-IN',  # English (India)
    'hi': 'hi-IN',  # Hindi (India)
    'bn': 'bn-IN'   # Bengali (India)
}

# Voice configurations for each language
VOICE_CONFIG = {
    'en-IN': {
        'name': 'en-IN-Standard-A',  # Female voice
        'gender': texttospeech.SsmlVoiceGender.FEMALE
    },
    'hi-IN': {
        'name': 'hi-IN-Standard-A',  # Female voice
        'gender': texttospeech.SsmlVoiceGender.FEMALE
    },
    'bn-IN': {
        'name': 'bn-IN-Standard-A',  # Female voice
        'gender': texttospeech.SsmlVoiceGender.FEMALE
    }
}


class SpeechService:
    """Service for handling Speech-to-Text and Text-to-Speech operations."""
    
    def __init__(self):
        """Initialize speech and TTS clients with service account credentials."""
        self.speech_client = None
        self.tts_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Google Cloud clients with credentials."""
        try:
            # Set credentials path from environment
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'speech_key.json')
            
            # Convert to absolute path if relative
            if not os.path.isabs(credentials_path):
                base_dir = Path(__file__).resolve().parent.parent
                credentials_path = str(base_dir / credentials_path)
            
            # Set environment variable for Google Cloud libraries
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            if not os.path.exists(credentials_path):
                logger.error(f"Service account key file not found: {credentials_path}")
                return
            
            # Load credentials
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/speech-to-text',
                    'https://www.googleapis.com/auth/text-to-speech'
                ]
            )
            
            # Initialize clients
            self.speech_client = speech.SpeechClient(credentials=credentials)
            self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
            
            logger.info("✓ Speech and TTS clients initialized successfully")
            logger.info(f"✓ Using credentials: {credentials_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize speech clients: {str(e)}")
            logger.exception("Speech client initialization error:")
    
    def transcribe_audio(
        self, 
        audio_content: bytes, 
        language_code: str = 'en'
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Transcribe audio to text using Google Speech-to-Text.
        
        Args:
            audio_content: Audio file content as bytes (WebM/Opus format)
            language_code: Language code ('en', 'hi', 'bn')
            
        Returns:
            Tuple of (transcribed_text, error_message)
        """
        if not self.speech_client:
            return None, "Speech client not initialized"
        
        try:
            # Get Google language code
            gcp_language = LANGUAGE_CODES.get(language_code, 'en-IN')
            
            logger.info(f"Transcribing audio: {len(audio_content)} bytes, language: {gcp_language}")
            
            # Configure audio
            audio = speech.RecognitionAudio(content=audio_content)
            
            # Configure recognition settings
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,  # WebM Opus default
                language_code=gcp_language,
                enable_automatic_punctuation=True,
                model='default',
                use_enhanced=True  # Use enhanced model for better accuracy
            )
            
            # Perform transcription
            response = self.speech_client.recognize(config=config, audio=audio)
            
            # Extract transcribed text
            if not response.results:
                logger.warning("No transcription results returned")
                return None, "No speech detected in audio"
            
            # Get the first (most confident) result
            transcript = response.results[0].alternatives[0].transcript
            confidence = response.results[0].alternatives[0].confidence
            
            logger.info(f"✓ Transcription successful: '{transcript}' (confidence: {confidence:.2f})")
            
            return transcript, None
            
        except Exception as e:
            error_msg = f"Transcription error: {str(e)}"
            logger.error(error_msg)
            logger.exception("Transcription exception:")
            return None, error_msg
    
    def synthesize_speech(
        self, 
        text: str, 
        language_code: str = 'en'
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Convert text to speech using Google Text-to-Speech.
        
        Args:
            text: Text to convert to speech
            language_code: Language code ('en', 'hi', 'bn')
            
        Returns:
            Tuple of (audio_content_bytes, error_message)
        """
        if not self.tts_client:
            return None, "TTS client not initialized"
        
        try:
            # Get Google language code
            gcp_language = LANGUAGE_CODES.get(language_code, 'en-IN')
            
            logger.info(f"Synthesizing speech: {len(text)} chars, language: {gcp_language}")
            
            # Get voice configuration
            voice_config = VOICE_CONFIG.get(gcp_language, VOICE_CONFIG['en-IN'])
            
            # Set the text input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=gcp_language,
                name=voice_config['name'],
                ssml_gender=voice_config['gender']
            )
            
            # Select the audio file type
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,  # Normal speed
                pitch=0.0,  # Normal pitch
                volume_gain_db=0.0  # Normal volume
            )
            
            # Perform the text-to-speech request
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            logger.info(f"✓ Speech synthesis successful: {len(response.audio_content)} bytes")
            
            return response.audio_content, None
            
        except Exception as e:
            error_msg = f"Speech synthesis error: {str(e)}"
            logger.error(error_msg)
            logger.exception("Speech synthesis exception:")
            return None, error_msg
    
    def is_available(self) -> bool:
        """Check if speech services are available."""
        return self.speech_client is not None and self.tts_client is not None


# Singleton instance
_speech_service = None

def get_speech_service() -> SpeechService:
    """Get or create the speech service singleton."""
    global _speech_service
    if _speech_service is None:
        _speech_service = SpeechService()
    return _speech_service
