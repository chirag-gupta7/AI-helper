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

# Check if ElevenLabs is installed and import it
try:
    from elevenlabs import generate, play, set_api_key, voices
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    # Import ElevenLabs Agent API
    from elevenlabs.conversational_ai import ConversationalAI
    ELEVENLABS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("ElevenLabs imports successful - Agent API available")
except ImportError as e:
    ELEVENLABS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"ElevenLabs not available: {e}")
    print("ElevenLabs not installed. Run 'pip install elevenlabs' to use ElevenLabs TTS.")

# Check if pyttsx3 is installed and import it
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("pyttsx3 not installed. Run 'pip install pyttsx3' to use fallback TTS.")

# Set up logging
logger = logging.getLogger(__name__)

# Load ElevenLabs configuration from environment variables
API_KEY = os.environ.get("ELEVENLABS_API_KEY")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel voice
AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID")

# Validate configuration
logger.info(f"ElevenLabs Configuration:")
logger.info(f"- API Key: {'✓ SET' if API_KEY and API_KEY != 'sk_' else '✗ NOT SET'}")
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
                response = self.conversational_ai.generate_response(
                    message=text,
                    voice_id=self.voice_id
                )
                
                # Play the agent's audio response
                if hasattr(response, 'audio') and response.audio:
                    play(response.audio)
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
                
                play(audio)
                logger.info(f"✓ Standard TTS successful: {text[:50]}...")
                return True
                
            except Exception as e:
                logger.error(f"✗ Standard TTS failed: {e}")
                
        return False

# Global agent instance
elevenlabs_agent = None

def initialize_elevenlabs_agent():
    """Initialize the ElevenLabs agent with proper error handling"""
    global elevenlabs_agent
    
    if not ELEVENLABS_AVAILABLE:
        logger.error("✗ ElevenLabs not available - please install: pip install elevenlabs")
        return False
        
    if not API_KEY or API_KEY.startswith('sk_') and len(API_KEY) < 10:
        logger.error("✗ Invalid ElevenLabs API key")
        return False
    
    try:
        elevenlabs_agent = ElevenLabsAgent(voice_id=VOICE_ID, agent_id=AGENT_ID)
        
        # Test the agent
        if elevenlabs_agent.client:
            logger.info("✓ ElevenLabs agent initialized successfully")
            return True
        else:
            logger.error("✗ Failed to initialize ElevenLabs client")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error initializing ElevenLabs agent: {e}")
        return False

def generate_speech(text: str, voice_id: str = None) -> bool:
    """Generate and play speech using ElevenLabs with proper fallback"""
    try:
        # Try ElevenLabs Agent first
        global elevenlabs_agent
        if elevenlabs_agent:
            success = elevenlabs_agent.speak_with_agent(text, "Voice assistant conversation")
            if success:
                return True
        
        # Direct ElevenLabs API fallback
        if ELEVENLABS_AVAILABLE and API_KEY:
            voice = voice_id or VOICE_ID
            try:
                logger.info("🔊 Trying direct ElevenLabs API...")
                client = ElevenLabs(api_key=API_KEY)
                
                audio = client.generate(
                    text=text,
                    voice=voice,
                    model="eleven_multilingual_v2",
                    voice_settings=VoiceSettings(
                        stability=0.5,
                        similarity_boost=0.8,
                        style=0.2,
                        use_speaker_boost=True
                    )
                )
                
                play(audio)
                logger.info(f"✓ Direct ElevenLabs successful: {text[:50]}...")
                return True
                
            except Exception as e:
                logger.error(f"✗ Direct ElevenLabs failed: {e}")
                logger.info("🔄 Falling back to pyttsx3...")
        else:
            logger.warning("⚠️  ElevenLabs not available, using pyttsx3...")
            
        # pyttsx3 fallback
        if PYTTSX3_AVAILABLE:
            try:
                logger.info("🔊 Using pyttsx3 fallback...")
                engine = pyttsx3.init()
                
                # Better voice settings
                engine.setProperty('rate', 165)
                engine.setProperty('volume', 0.95)
                
                # Select best voice
                voices = engine.getProperty('voices')
                if voices:
                    # Prefer female or higher quality voices
                    selected_voice = voices[0]
                    for voice in voices:
                        voice_name = voice.name.lower()
                        if any(name in voice_name for name in ['zira', 'hazel', 'female', 'cortana']):
                            selected_voice = voice
                            break
                    engine.setProperty('voice', selected_voice.id)
                    logger.info(f"Using voice: {selected_voice.name}")
                
                engine.say(text)
                engine.runAndWait()
                logger.info(f"✓ pyttsx3 successful: {text[:50]}...")
                return True
                
            except Exception as fallback_e:
                logger.error(f"✗ pyttsx3 failed: {fallback_e}")
                logger.info(f"📝 Text only: {text}")
                return False
        else:
            logger.error("✗ No TTS methods available")
            return False
            
    except Exception as e:
        logger.error(f"✗ Critical error in speech generation: {e}")
        logger.error(traceback.format_exc())
        return False

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
        global elevenlabs_agent
        if not elevenlabs_agent:
            agent_initialized = initialize_elevenlabs_agent()
            if agent_initialized:
                logger.info("✓ ElevenLabs agent ready for SimpleVoiceAssistant")
            else:
                logger.warning("⚠️  ElevenLabs agent not available, using fallback")

    def speak(self, text):
        """Speak using ElevenLabs agent with comprehensive fallback"""
        success = False
        
        logger.info(f"🗣️  Speaking: {text[:100]}...")
        
        # Try ElevenLabs agent first
        if elevenlabs_agent:
            success = elevenlabs_agent.speak_with_agent(text, "Voice assistant conversation")
        
        # Fallback to generate_speech function
        if not success:
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
                schedule = get_today_schedule(self.user_id)
                if schedule:
                    return f"Here's your schedule for today: {schedule}"
                else:
                    return "You have no scheduled events for today."
            except Exception as e:
                logger.error(f"Error getting schedule: {e}")
                return "I couldn't retrieve your schedule right now."
        
        if "next meeting" in transcript_lower:
            try:
                next_meeting = get_next_meeting(self.user_id)
                if next_meeting:
                    return f"Your next meeting is: {next_meeting}"
                else:
                    return "You don't have any upcoming meetings."
            except Exception as e:
                logger.error(f"Error getting next meeting: {e}")
                return "I couldn't check your next meeting right now."
        
        if "free time" in transcript_lower:
            try:
                free_time = get_free_time_today(self.user_id)
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
        
        # Initialize ElevenLabs agent
        agent_initialized = initialize_elevenlabs_agent()
        if agent_initialized:
            logger.info("✓ ElevenLabs conversational agent initialized successfully")
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
                created_at=datetime.now(timezone.utc)
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

        # Initialize ElevenLabs agent
        agent_initialized = initialize_elevenlabs_agent()
        if agent_initialized:
            self._log_to_frontend("✅ ElevenLabs Agent initialized", 'success')
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
                self._log_to_database(self.user_id, 'AGENT', response_text, self.conversation_id)
                
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
    
    # Initialize agent
    success = initialize_elevenlabs_agent()
    if success:
        logger.info("✅ Agent initialization successful")
        
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

# END OF voice_assistant.py