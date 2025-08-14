"""
ElevenLabs Integration Module
Handles all interactions with the ElevenLabs API
"""

import os
import logging
import sys
import time
from typing import Optional

# Setup logging
logger = logging.getLogger(__name__)

# Constants for ElevenLabs
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
MAX_RETRIES = 3
RETRY_DELAY = 2

# Flag to track availability
elevenlabs_available = False

# Try to import ElevenLabs packages with better error handling
try:
    # We now import the client and not the top-level 'generate' function
    from elevenlabs.client import ElevenLabs
    from elevenlabs import Voice, VoiceSettings
    
    elevenlabs_available = True
    logger.info("✅ ElevenLabs package successfully imported")
except ImportError as e:
    elevenlabs_available = False
    logger.warning(f"⚠️ ElevenLabs package not available: {e}")
    logger.warning("⚠️ To use ElevenLabs, install with: pip install elevenlabs")

class ElevenLabsService:
    """Service class for ElevenLabs TTS functionality"""
    
    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        self.voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        self.client = None
        self.initialized = False
        self.subscription_info = None
        
    def initialize(self) -> bool:
        """Initialize the ElevenLabs service with proper error handling and retry logic"""
        if not elevenlabs_available:
            logger.warning("⚠️ ElevenLabs package not available. Cannot initialize.")
            return False
            
        if not self.api_key:
            logger.warning("⚠️ ElevenLabs API key not set in environment variables.")
            return False
        
        # Try to initialize with retries
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Attempt {attempt+1}/{MAX_RETRIES} to initialize ElevenLabs...")
                
                # Create client (API key is passed directly to the client)
                self.client = ElevenLabs(api_key=self.api_key)
                
                # Test connection by getting user info
                user_data = self.client.user.get()
                
                if user_data:
                    self.subscription_info = {
                        "tier": user_data.subscription.tier,
                        "character_limit": user_data.subscription.character_limit,
                        "character_count": user_data.subscription.character_count,
                        "remaining_characters": user_data.subscription.character_limit - user_data.subscription.character_count
                    }
                    
                    logger.info(f"✅ ElevenLabs initialized successfully!")
                    logger.info(f"✅ Subscription: {self.subscription_info['tier']}")
                    logger.info(f"✅ Characters remaining: {self.subscription_info['remaining_characters']}/{self.subscription_info['character_limit']}")
                    
                    self.initialized = True
                    return True
                    
            except Exception as e:
                logger.error(f"❌ ElevenLabs initialization error (attempt {attempt+1}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"⏳ Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
        
        logger.error(f"❌ Failed to initialize ElevenLabs after {MAX_RETRIES} attempts")
        return False
    
    def generate_speech(self, text: str) -> Optional[bytes]:
        """Generate speech from text using ElevenLabs"""
        if not self.initialized or not self.client:
            logger.warning("⚠️ ElevenLabs service not initialized")
            return None
            
        try:
            # Filter problematic characters from the text to prevent issues
            filtered_text = ''.join(c for c in text if ord(c) < 65536)
            
            # Use the updated API method for ElevenLabs 2.9.2+
            audio = self.client.text_to_speech.convert(
                text=filtered_text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2",
                output_format="mp3_44100_128"
            )
            
            logger.info(f"✅ Speech generated successfully for: {filtered_text[:50]}...")
            return audio
            
        except Exception as e:
            logger.error(f"❌ ElevenLabs speech generation error: {str(e)}")
            return None
    
    def get_available_voices(self):
        """Get list of available voices from ElevenLabs"""
        if not self.initialized or not self.client:
            logger.warning("⚠️ ElevenLabs service not initialized")
            return []
            
        try:
            voices = self.client.voices.get_all()
            return [{"id": voice.voice_id, "name": voice.name} for voice in voices]
            
        except Exception as e:
            logger.error(f"❌ ElevenLabs get voices error: {str(e)}")
            return []
