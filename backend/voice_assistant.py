# backend/voice_assistant.py
"""
Enhanced Voice Assistant with ElevenLabs Agent Integration
"""
import os
import sys
import traceback
import logging
import time
from threading import Thread, Event
import queue
import json
from datetime import datetime, timezone
import re
import uuid
import threading
from typing import Optional, Callable
from flask import Flask
import io
import wave

# Check if PyAudio is installed and import it
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("PyAudio not installed. Run 'pip install pyaudio' for audio playback support.")

# Set UTF-8 encoding for stdout/stderr to fix encoding errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr.encoding != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


# Setup logging
logger = logging.getLogger(__name__)

# Import our improved ElevenLabs integration
from .elevenlabs_integration import ElevenLabsService, elevenlabs_available

# Check if ElevenLabs is installed and import it with improved error handling
try:
    from elevenlabs import generate, set_api_key, Voice, VoiceSettings
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai import ConversationalAI
    ELEVENLABS_AVAILABLE = True
    logger.info("ElevenLabs package successfully imported")
except ImportError as e:
    ELEVENLABS_AVAILABLE = False
    logger.warning(f"ElevenLabs package not available: {e}, will use pyttsx3 fallback")

# Check if pyttsx3 is installed and import it
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("pyttsx3 not installed. Run 'pip install pyttsx3' to use fallback TTS.")

# Check for pydub to handle audio playback
try:
    from pydub import AudioSegment
    from pydub.playback import play as pydub_play
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("pydub not installed. Run 'pip install pydub' for enhanced audio playback.")
    
# Load ElevenLabs configuration from environment variables
API_KEY = os.environ.get("ELEVENLABS_API_KEY")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel voice
AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID")

# Validate configuration
logger.info(f"ElevenLabs Configuration:")
logger.info(f"- API Key: {'✓ SET' if API_KEY and len(API_KEY) > 10 else '✗ NOT SET'}")
logger.info(f"- Voice ID: {VOICE_ID}")
logger.info(f"- Agent ID: {'✓ SET' if AGENT_ID else '✗ NOT SET'}")
logger.info(f"- ElevenLabs Available: {ELEVENLABS_AVAILABLE}")

# Configure ElevenLabs API
if ELEVENLABS_AVAILABLE and API_KEY:
    try:
        set_api_key(API_KEY)
        logger.info("✓ ElevenLabs API key configured successfully")
    except Exception as e:
        logger.error(f"✗ Error configuring ElevenLabs API key: {e}")

from .memory import ConversationMemory, ConversationContext
from .models import Conversation as DBConversation, Message, MessageType, db, User, Log
from .command_processor import VoiceCommandProcessor, set_flask_app_for_command_processor
from .google_calendar_integration import (
    get_today_schedule,
    create_event_from_conversation,
    get_upcoming_events,
    get_next_meeting,
    get_free_time_today
)
# ElevenLabs Agent Implementation
class ElevenLabsAgent:
    """ElevenLabs Conversational Agent Implementation with proper Agent API"""
    
    def __init__(self, voice_id: str = None, agent_id: str = None):
        self.voice_id = voice_id or VOICE_ID
        self.agent_id = agent_id or AGENT_ID
        self.client = None
        self.conversational_ai = None
        
        if ELEVENLABS_AVAILABLE and API_KEY:
            try:
                # Initialize ElevenLabs client
                self.client = ElevenLabs(api_key=API_KEY)
                
                # Initialize Conversational AI Agent if agent_id is provided
                if self.agent_id:
                    try:
                        self.conversational_ai = ConversationalAI(
                            agent_id=self.agent_id,
                            api_key=API_KEY
                        )
                        logger.info(f"✓ ElevenLabs Agent initialized successfully:")
                        logger.info(f"  - Agent ID: {self.agent_id}")
                        logger.info(f"  - Voice ID: {self.voice_id}")
                    except Exception as agent_e:
                        logger.warning(f"Agent API failed, using standard TTS: {agent_e}")
                        self.conversational_ai = None
                else:
                    logger.warning("No Agent ID provided, using standard TTS")
                    
            except Exception as e:
                logger.error(f"✗ Failed to initialize ElevenLabs client: {e}")
    
    def speak_with_agent(self, text: str, context: str = None) -> bool:
        """Use ElevenLabs conversational agent for natural speech"""
        
        # Try Agent API first
        if self.conversational_ai:
            try:
                logger.info("🎤 Using ElevenLabs Agent API...")
                
                # Use the agent to generate and play response
                # Note: This is simplified as the Agent API can be complex.
                # In a real app, you'd handle the streaming response.
                response = self.conversational_ai.generate_response(
                    message=text,
                    voice_id=self.voice_id
                )
                
                # Play the agent's audio response
                # This assumes the response is a stream or a complete audio object
                audio_stream = response.audio_stream if hasattr(response, 'audio_stream') else response.audio
                if audio_stream:
                    _play_audio_stream(audio_stream)
                    logger.info(f"✓ Agent spoke successfully: {text[:50]}...")
                return True
                    
            except Exception as e:
                logger.error(f"✗ ElevenLabs Agent API error: {e}")
                logger.info("🔄 Falling back to standard TTS...")
        
        # Fallback to standard ElevenLabs TTS
        if self.client:
            try:
                logger.info("🔊 Using ElevenLabs standard TTS...")
                
                audio = self.client.generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_turbo_v2",
                    voice_settings=VoiceSettings(
                        stability=0.5,
                        similarity_boost=0.8,
                        style=0.3,
                        use_speaker_boost=True
                    )
                )
                
                _play_audio_stream(audio)
                logger.info(f"✓ Standard TTS successful: {text[:50]}...")
                return True
                
            except Exception as e:
                logger.error(f"✗ Standard TTS error: {e}")
                return False
def _play_audio_stream(audio_stream):
    """Play a streaming audio response using PyAudio with improved error handling"""
    if not PYAUDIO_AVAILABLE:
        logger.error("❌ PyAudio not available. Cannot play audio stream.")
        return False
        
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                      channels=1,
                      rate=22050,
                      output=True)
                      
        # Process the stream safely
        try:
            with audio_stream as stream_source:
                for chunk in stream_source:
                    if chunk:
                        stream.write(chunk)
        except Exception as stream_error:
            logger.error(f"❌ Error processing audio stream: {stream_error}")
            return False
            
        # Clean up resources
        stream.stop_stream()
        stream.close()
        p.terminate()
        return True
    except Exception as e:
        logger.error(f"❌ Error setting up audio playback: {e}")
        return False

# Global ElevenLabs service instance
elevenlabs_service = ElevenLabsService()

def initialize_elevenlabs_service():
    """Initialize ElevenLabs service with API key from environment variables."""
    global elevenlabs_service
    
    if not elevenlabs_available:
        logger.warning("⚠️ ElevenLabs package not available")
        return False
    
    try:
        success = elevenlabs_service.initialize()
        if success:
            logger.info("✅ ElevenLabs service initialized successfully")
            return True
        else:
            logger.warning("⚠️ ElevenLabs service initialization failed")
            return False
    except Exception as e:
        logger.error(f"❌ Error initializing ElevenLabs service: {e}")
        return False
    
def generate_speech(text_to_speak):
    """Generate speech from text using available TTS engines"""
    
    # Remove all emojis and problematic Unicode characters
    emoji_pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map symbols
                           u"\U0001F700-\U0001F77F"  # alchemical symbols
                           u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                           u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                           u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                           u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                           u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                           u"\U00002702-\U000027B0"  # Dingbats
                           u"\U000024C2-\U0001F251" 
                           "]+", flags=re.UNICODE)
    
    filtered_text = emoji_pattern.sub(r'', text_to_speak)
    
    # Try ElevenLabs first
    if elevenlabs_available and elevenlabs_service.initialized:
        try:
            logger.info("🔊 Using ElevenLabs for speech...")
            audio_stream = elevenlabs_service.generate_speech(filtered_text)
            
            if audio_stream:
                success = _play_audio_stream(audio_stream)
                if success:
                    logger.info(f"✅ ElevenLabs speech successful: {filtered_text[:50]}...")
                    return True
                else:
                    logger.warning("⚠️ Failed to play ElevenLabs audio stream")
            else:
                logger.warning("⚠️ ElevenLabs returned empty audio stream")
                
        except Exception as e:
            logger.error(f"❌ ElevenLabs error: {str(e)}")
            
    # Fall back to pyttsx3
    logger.info("🔊 Using pyttsx3 fallback...")
    return _fallback_pyttsx3(filtered_text)


def _fallback_pyttsx3(text_to_speak):
    """Fallback to pyttsx3 for speech generation."""
    if not PYTTSX3_AVAILABLE:
        logger.error("❌ pyttsx3 is not available. Cannot generate speech.")
        return False
        
    try:
        # Initialize the pyttsx3 engine
        engine = pyttsx3.init()
        
        # Filter out emojis and other problematic Unicode characters completely
        # This is more robust than the current approach that only handles ASCII
        import re
        # Remove all emojis and special Unicode characters
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"  # emoticons
                                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                   u"\U0001F700-\U0001F77F"  # alchemical symbols
                                   u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                                   u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                                   u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                                   u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                                   u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                                   u"\U00002702-\U000027B0"  # Dingbats
                                   u"\U000024C2-\U0001F251" 
                                   "]+", flags=re.UNICODE)
        
        safe_text = emoji_pattern.sub(r'', text_to_speak)
        # Additional safety - only keep printable ASCII characters if still having issues
        safe_text = ''.join(c for c in safe_text if ord(c) < 127)
        
        # Set properties (optional)
        engine.setProperty('rate', 180)  # Speed of speech
        engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Speak the text
        engine.say(safe_text)
        engine.runAndWait()
        
        logger.info(f"🔊 pyttsx3 successful: {safe_text[:50]}...")
        return True
    except Exception as e:
        logger.error(f"❌ pyttsx3 error: {str(e)}")
        return False
    

def _play_audio_file(file_path):
    """Play an audio file."""
    if not PYDUB_AVAILABLE:
        logger.error("❌ pydub not available. Cannot play audio file.")
        return False
        
    try:
        song = AudioSegment.from_file(file_path)
        pydub_play(song)
        return True
    except Exception as e:
        logger.error(f"❌ pydub error playing audio file: {e}")
        return False

def _play_text_via_modern_api(text_to_speak, voice="Rachel"):
    """Play text using modern API approach."""
    success = generate_speech(text_to_speak, voice)
    return success

# Global variables for Flask app context and callbacks
_flask_app_instance = None
_on_status_change: Optional[Callable] = None
_on_log: Optional[Callable] = None
_on_log_to_db: Optional[Callable] = None

# Global state for the voice assistant thread
conversation_active = False
current_user_id = None
current_conversation_id = None
current_voice_assistant = None

def _update_status(status: str, message: str):
    """Update status using callback if available"""
    if _on_status_change:
        _on_status_change(status, message)
    logger.info(f"Status: {status} - {message}")

class SimpleVoiceAssistant:
    """Simple voice assistant using ElevenLabs Agent"""

    def __init__(self, user_id, conversation_id):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.is_listening = False
        self.user_transcript_queue = queue.Queue()
        
        # Initialize ElevenLabs agent
        global elevenlabs_service
        if not elevenlabs_service.initialized:
            agent_initialized = initialize_elevenlabs_service()
            if agent_initialized:
                logger.info("✓ ElevenLabs agent ready for SimpleVoiceAssistant")
            else:
                logger.warning("⚠️  ElevenLabs agent not available, using fallback")

    def speak(self, text):
        """Speak using ElevenLabs agent with comprehensive fallback"""
        success = False
        
        logger.info(f"🗣️  Speaking: {text[:100]}...")
        
        # Use the improved generate_speech function which handles ElevenLabs and fallback
        success = generate_speech(text)
        
        # Log result
        if success:
            _log_and_commit(self.user_id, 'INFO', f"✓ Agent spoke: {text[:50]}...", self.conversation_id)
        else:
            _log_and_commit(self.user_id, 'ERROR', f"✗ Failed to speak: {text[:50]}...", self.conversation_id)

    def process_voice_input(self, text_input):
        """Process voice input from the user."""
        if not text_input or not isinstance(text_input, str):
            logger.warning("⚠️  Received empty or invalid input")
            return "I didn't catch that. Could you please repeat?"
        
        # Log the input
        logger.info(f"👤 User: {text_input}")
        _log_and_commit(self.user_id, 'USER', text_input, self.conversation_id)
        
        try:
            # Get user information
            user = User.query.get(self.user_id)
            user_name = user.username if user else "User"
            
            # Process input and generate response
            response = self._process_input_with_agent(text_input, user_name)
            
            # Speak the response
            self.speak(response)
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing input: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            _log_and_commit(self.user_id, 'ERROR', error_msg, self.conversation_id)
            return "I encountered an error processing your request. Please try again."

    def _process_input_with_agent(self, text_input, user_name):
        """Process input and generate a response using the agent logic."""
        return self._simulate_llm_response(text_input)
    
    def _simulate_llm_response(self, transcript):
        """Enhanced LLM response simulation"""
        transcript_lower = transcript.lower()

        # Calendar commands
        if "schedule" in transcript_lower and "meeting" in transcript_lower:
            return "I can help you schedule a meeting. Please tell me the details like who, when, and where."
        
        if any(phrase in transcript_lower for phrase in ["today's schedule", "my schedule today", "schedule for today"]):
            try:
                schedule = get_today_schedule()
                if schedule:
                    return f"Here's your schedule for today: {schedule}"
                else:
                    return "You have no scheduled events for today."
            except Exception as e:
                logger.error(f"Error getting schedule: {e}")
                return "I couldn't retrieve your schedule right now."
        
        if "next meeting" in transcript_lower:
            try:
                next_meeting = get_next_meeting()
                if next_meeting:
                    return f"Your next meeting is: {next_meeting}"
                else:
                    return "You don't have any upcoming meetings."
            except Exception as e:
                logger.error(f"Error getting next meeting: {e}")
                return "I couldn't check your next meeting right now."
        
        if "free time" in transcript_lower:
            try:
                free_time = get_free_time_today()
                if free_time:
                    return f"Your free time today: {free_time}"
                else:
                    return "Your schedule is quite busy today."
            except Exception as e:
                logger.error(f"Error getting free time: {e}")
                return "I couldn't check your free time right now."
        
        # Other commands
        if "weather" in transcript_lower:
            return "I'll get the weather information for you."
        
        if "news" in transcript_lower:
            return "Let me get the latest news for you."
        
        if "remind me to" in transcript_lower:
            return f"I'll set a reminder for you: {transcript}"
        
        if "timer for" in transcript_lower:
            return f"Setting a timer now: {transcript}"

        # Conversation end
        if any(phrase in transcript_lower for phrase in ["goodbye", "end chat", "that's all", "thanks bye", "stop", "see you later"]):
            return "Goodbye! Have a great day. CONVERSATION_END"

        # Default response
        return "I'm here to help! You can ask about your schedule, weather, news, or I can set reminders and timers for you."

def log_voice_to_database(user_id, level, message, conversation_id):
    """Log to database using global callback"""
    if _on_log_to_db:
        _on_log_to_db(user_id, level, message, conversation_id)

def _log_and_commit(user_id, level, message, conversation_id):
    """Helper to log and commit within an app context"""
    log_voice_to_database(user_id, level, message, conversation_id=conversation_id)

def process_voice_command(text_input):
    """Process voice command with the simple voice assistant"""
    global current_voice_assistant, conversation_active, current_user_id, current_conversation_id

    if not current_voice_assistant:
        logger.error("✗ Voice assistant not active")
        return "Voice assistant is not active"

    try:
        response = current_voice_assistant.process_voice_input(text_input)

        if "CONVERSATION_END" in response:
            logger.info("🛑 Ending conversation as requested...")
            _log_and_commit(current_user_id, 'INFO', "Voice conversation ended by user request", current_conversation_id)
            conversation_active = False
            current_voice_assistant = None

        return response

    except Exception as e:
        logger.error(f"✗ Error processing voice command: {e}")
        logger.error(traceback.format_exc())
        return f"I encountered an error: {str(e)}"

def _start_voice_assistant_internal(user_id: uuid.UUID):
    """Start the voice assistant with proper ElevenLabs agent setup"""
    global current_voice_assistant, current_user_id, current_conversation_id
    
    try:
        current_user_id = user_id
        
        # Initialize ElevenLabs service
        agent_initialized = initialize_elevenlabs_service()
        if agent_initialized:
            logger.info("✓ ElevenLabs service initialized successfully")
        else:
            logger.warning("⚠️  ElevenLabs agent not available, using fallback TTS")
        
        # Get user information
        user = User.query.get(user_id)
        user_name = user.username if user else "User"
        
        # Create new conversation
        with _flask_app_instance.app_context():
            new_db_conversation = DBConversation(
                user_id=user_id,
                title=f"Voice Chat - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                started_at=datetime.now(timezone.utc)
            )
            db.session.add(new_db_conversation)
            db.session.commit()
            current_conversation_id = new_db_conversation.id

        # Create voice assistant instance
        current_voice_assistant = SimpleVoiceAssistant(user_id, current_conversation_id)

        logger.info("🚀 Starting ElevenLabs Agent Voice Assistant...")
        _log_and_commit(current_user_id, 'INFO', "Voice assistant with ElevenLabs agent starting", current_conversation_id)

        # Enhanced greeting
        if agent_initialized:
            initial_greeting = f"Hello {user_name}! I'm your AI voice assistant powered by ElevenLabs Agent. I can help you with calendar events, weather, news, and much more. What would you like me to help you with today?"
        else:
            initial_greeting = f"Hello {user_name}! I'm your AI voice assistant. I can help you with calendar events, weather, and much more. What would you like me to help you with today?"
            
        current_voice_assistant.speak(initial_greeting)
        
        # Start listening
        current_voice_assistant.is_listening = True
        _update_status("active", f"Voice assistant active for {user_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error starting voice assistant: {e}")
        logger.error(traceback.format_exc())
        _log_and_commit(user_id, 'ERROR', f"Failed to start voice assistant: {str(e)}", None)
        _update_status("error", f"Failed to start: {str(e)}")
        return False

def start_voice_assistant(user_id: uuid.UUID, app_instance: Flask, retries: int = 3, delay: int = 5):
    """Public function to start the voice assistant with retry logic"""
    global _flask_app_instance, conversation_active
    _flask_app_instance = app_instance
    set_flask_app_for_command_processor(app_instance)
    conversation_active = True

    for attempt in range(retries):
        try:
            logger.info(f"🔄 Attempt {attempt + 1}/{retries} to start voice assistant for user {user_id}")
            with app_instance.app_context():
                success = _start_voice_assistant_internal(user_id)
                if success:
                    logger.info("✅ Voice assistant started successfully.")
                    
                    # Keep the session alive
                    while conversation_active:
                        time.sleep(1)
                    return
                else:
                    raise Exception("Failed to initialize voice assistant")
        except KeyboardInterrupt:
            logger.info("⌨️  Keyboard interrupt detected. Ending conversation...")
            _log_and_commit(user_id, 'INFO', "Voice conversation interrupted by keyboard", current_conversation_id)
            conversation_active = False
            break
        except Exception as e:
            logger.error(f"✗ Failed to start voice assistant on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"💥 All {retries} attempts failed to start voice assistant for user {user_id}.")
                log_voice_to_database(user_id, 'CRITICAL', f"Voice assistant failed to start after {retries} attempts: {str(e)}", conversation_id=None)
                raise
        finally:
            if _flask_app_instance:
                try:
                    db.session.remove()
                    logger.info("🧹 Database session cleaned up.")
                except Exception as cleanup_e:
                    logger.error(f"✗ Error cleaning up database session: {cleanup_e}")

# Keep existing VoiceAssistant class for compatibility
class VoiceAssistant:
    def __init__(self, app_instance, on_status_change, on_log, on_log_to_db):
        global _flask_app_instance, _on_status_change, _on_log, _on_log_to_db
        _flask_app_instance = app_instance
        _on_status_change = on_status_change
        _on_log = on_log
        _on_log_to_db = on_log_to_db
        set_flask_app_for_command_processor(app_instance)

        self.listening_thread = None
        self.is_listening = False
        self.status = "Inactive"
        self.user_id = None
        self.conversation_id = None
        self.user_transcript_queue = queue.Queue()

    def _log_to_frontend(self, message, level):
        """Logs a message to the console and sends it to the frontend via callback."""
        if _on_log:
            try:
                _on_log(message, level)
            except Exception as e:
                logger.error(f"Error in frontend log callback: {str(e)}")

    def _log_to_database(self, user_id, level, message, conversation_id=None):
        """Logs voice-related events to the database using the callback."""
        if _on_log_to_db:
            _on_log_to_db(user_id, level, message, conversation_id)

    def _play_text_via_modern_api(self, text_to_speak, voice=None):
        """Generates and plays audio using ElevenLabs."""
        try:
            success = generate_speech(text_to_speak, voice)
            if success:
                self._log_to_frontend(f"✓ Successfully played: {text_to_speak[:50]}...", 'info')
            else:
                self._log_to_frontend(f"⚠️  Audio failed, text: {text_to_speak}", 'warning')
        except Exception as e:
            logger.error(f"Error in _play_text_via_modern_api: {e}")
            self._log_to_frontend(f"✗ Error playing audio: {str(e)}", 'error')

    def start_listening(self, user_id):
        """Starts the voice assistant in a separate thread."""
        if self.is_listening:
            return False, "Voice assistant is already listening"

        self.user_id = user_id
        self.is_listening = True
        self.status = "Listening"
        self._log_to_frontend("🚀 Starting voice assistant...", 'info')

        # Initialize ElevenLabs service
        agent_initialized = initialize_elevenlabs_service()
        if agent_initialized:
            self._log_to_frontend("✅ ElevenLabs Service initialized", 'success')
        else:
            self._log_to_frontend("⚠️  Using fallback TTS", 'warning')

        with _flask_app_instance.app_context():
            session_id = str(uuid.uuid4())
            new_db_conversation = DBConversation(user_id=user_id, session_id=session_id)
            db.session.add(new_db_conversation)
            db.session.commit()
            self.conversation_id = new_db_conversation.id

        self.listening_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listening_thread.start()

        return True, "Voice assistant started successfully"

    def _listening_loop(self):
        """The main listening and processing loop."""
        global conversation_active

        with _flask_app_instance.app_context():
            user = User.query.get(self.user_id)
            user_name = user.username if user else "User"

        self._log_to_frontend("🎧 Voice assistant session started.", 'success')
        self._log_to_frontend("👂 Listening for commands...", 'status')

        initial_greeting = "Hello! I'm your ElevenLabs powered voice assistant. How can I help you today?"
        self._play_text_via_modern_api(initial_greeting)

        while self.is_listening:
            try:
                transcript = self.user_transcript_queue.get(timeout=1)
                
                if transcript == "SHUTDOWN_SIGNAL":
                    self._log_to_frontend("🛑 Shutting down voice assistant...", 'status')
                    self.status = "Inactive"
                    break

                self._log_to_frontend(f"👤 User: {transcript}", 'info')
                self._log_to_database(self.user_id, 'USER', transcript, self.conversation_id)

                # Create simple assistant instance for processing
                simple_assistant = SimpleVoiceAssistant(self.user_id, self.conversation_id)
                response_text = simple_assistant._simulate_llm_response(transcript)
                
                self._log_to_frontend(f"🤖 Assistant: {response_text}", 'info')
                self._log_to_database(self.user_id, 'ASSISTANT', response_text, self.conversation_id)
                
                self._play_text_via_modern_api(response_text)

                if "CONVERSATION_END" in response_text:
                    self.is_listening = False
                    break

            except queue.Empty:
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in listening loop: {e}")
                logger.error(traceback.format_exc())
                self._log_to_frontend("💥 An unexpected error occurred.", 'error')

        self._log_to_frontend("👋 Voice assistant session ended.", 'info')
        self._log_to_database(self.user_id, 'INFO', "Voice assistant session ended.", self.conversation_id)

    def stop_listening(self):
        """Stops the voice assistant."""
        if not self.is_listening:
            return False, "Voice assistant is not currently active"

        self.is_listening = False
        self.status = "Inactive"
        self._log_to_frontend("🛑 Voice assistant stopped.", 'info')
        
        try:
            self.user_transcript_queue.put("SHUTDOWN_SIGNAL")
        except:
            pass
            
        return True, "Voice assistant stopped"

    def process_transcript(self, transcript):
        """Process a transcript input from the user."""
        if not self.is_listening:
            return False, "Voice assistant is not currently active"
        
        try:
            self.user_transcript_queue.put(transcript)
            return True, "Transcript processed successfully"
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            return False, f"Error processing transcript: {str(e)}"

    def get_status(self):
        """Returns the current status of the voice assistant."""
        return {
            'active': self.is_listening,
            'status': self.status,
            'user_id': str(self.user_id) if self.user_id else None,
            'is_listening': self.is_listening,
            'elevenlabs_available': ELEVENLABS_AVAILABLE,
            'api_key_set': bool(API_KEY and len(API_KEY) > 10),
            'agent_id_set': bool(AGENT_ID)
        }

# Test function for voice synthesis
def test_voice_synthesis():
    """Test function to verify ElevenLabs setup"""
    logger.info("🧪 Testing voice synthesis...")
    
    # Initialize service
    success = initialize_elevenlabs_service()
    if success:
        logger.info("✅ ElevenLabs service initialization successful")
        
        # Test speech
        test_text = "Hello! This is a test of the ElevenLabs voice synthesis system."
        speech_success = generate_speech(test_text)
        
        if speech_success:
            logger.info("✅ Voice synthesis test successful!")
            return True
        else:
            logger.error("❌ Voice synthesis test failed")
            return False
    else:
        logger.error("❌ Agent initialization failed")
        return False

def _listening_loop(self, initial_greeting=None):
    """Main listening loop for the voice assistant."""
    # Play initial greeting if provided
    if initial_greeting:
        self._play_text_via_modern_api(initial_greeting)
    
    # Continue with the rest of listening loop code
    # This function can be extended based on specific needs
    logger.info("🎧 Voice assistant listening loop started")

# END OF voice_assistant.py
