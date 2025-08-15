"""
Fixed ElevenLabs Agent Handler
Handles agent initialization without ConversationalAI dependency
"""
import os
import logging
import sys
from typing import Optional

# Clean logging setup
logger = logging.getLogger(__name__)

class FixedElevenLabsAgent:
    """Fixed ElevenLabs Agent that works without ConversationalAI"""
    
    def __init__(self, api_key: str = None, voice_id: str = None, agent_id: str = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.agent_id = agent_id or os.environ.get("ELEVENLABS_AGENT_ID")
        self.client = None
        self.initialized = False
        
        # Try to initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize the ElevenLabs client"""
        if not self.api_key:
            logger.warning("❌ No ElevenLabs API key provided")
            return False
        
        try:
            # Import ElevenLabs client
            from elevenlabs.client import ElevenLabs
            
            # Initialize client
            self.client = ElevenLabs(api_key=self.api_key)
            
            # Test connection
            user_info = self.client.user.get()
            if user_info:
                logger.info("✅ ElevenLabs agent initialized successfully!")
                logger.info(f"📊 Subscription: {getattr(user_info.subscription, 'tier', 'Unknown')}")
                self.initialized = True
                return True
            
        except ImportError as e:
            logger.error(f"❌ ElevenLabs package not available: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ElevenLabs agent: {e}")
        
        return False
    
    def generate_speech(self, text: str) -> Optional[bytes]:
        """Generate speech from text using ElevenLabs TTS"""
        if not self.initialized:
            logger.error("❌ Agent not initialized")
            return None
        
        try:
            logger.info(f"🔊 Generating speech for: {text[:50]}...")
            
            # Generate audio using TTS
            audio = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_monolingual_v1"
            )
            
            # Convert generator to bytes if needed
            if hasattr(audio, '__iter__') and not isinstance(audio, bytes):
                audio_bytes = b''.join(audio)
            else:
                audio_bytes = audio
            
            logger.info("✅ Speech generated successfully")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"❌ Speech generation failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if the agent is available and ready"""
        return self.initialized and self.client is not None
    
    def get_status(self) -> dict:
        """Get agent status information"""
        return {
            'initialized': self.initialized,
            'has_api_key': bool(self.api_key),
            'voice_id': self.voice_id,
            'agent_id': self.agent_id,
            'available': self.is_available()
        }

# Global instance
_fixed_agent = None

def get_fixed_agent() -> FixedElevenLabsAgent:
    """Get or create the global fixed agent instance"""
    global _fixed_agent
    if _fixed_agent is None:
        _fixed_agent = FixedElevenLabsAgent()
    return _fixed_agent

def initialize_fixed_agent() -> bool:
    """Initialize the fixed agent and return success status"""
    agent = get_fixed_agent()
    return agent.is_available()
