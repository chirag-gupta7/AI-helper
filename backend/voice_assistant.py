import os
from dotenv import load_dotenv
import logging # Ensure logging is imported here
import threading
import time
from flask import Flask # Import Flask for type hinting
import uuid
import traceback

# Import for ElevenLabs SDK
try:
    import elevenlabs
    from elevenlabs.client import ElevenLabs
    from elevenlabs import generate, play, stream, Voice, VoiceSettings
    
    # Check if we have the modern API
    if hasattr(elevenlabs, '__version__'):
        print(f"ElevenLabs SDK version: {elevenlabs.__version__}")
    
    ELEVENLABS_IMPORTS_SUCCESS = True
    
except ImportError as e:
    ELEVENLABS_IMPORTS_SUCCESS = False
    logging.error(f"CRITICAL: ElevenLabs imports failed: {e}. Voice functionality will be disabled.")
    logging.error(traceback.format_exc())
except Exception as e:
    ELEVENLABS_IMPORTS_SUCCESS = False
    logging.error(f"CRITICAL: Unexpected error during ElevenLabs setup: {e}. Voice functionality will be disabled.")
    logging.error(traceback.format_exc())


# Attempt to import pyttsx3 for fallback audio, if available
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logging.warning("pyttsx3 not found. Local TTS fallback will not be available.")


from .memory import ConversationMemory, ConversationContext
from .models import Conversation as DBConversation, Message, MessageType, db, User, Log
from .command_processor import VoiceCommandProcessor, set_flask_app_for_command_processor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__) # DEFINE LOGGER HERE

# Now you can safely use logger
if ELEVENLABS_IMPORTS_SUCCESS:
    logger.info(f"ElevenLabs SDK version {elevenlabs.__version__} loaded successfully.")


load_dotenv()

from .google_calendar_integration import (
    get_today_schedule,
    create_event_from_conversation,
)

_flask_app_instance: Flask = None

def set_flask_app(app_instance: Flask):
    """Sets the Flask app instance for use in background tasks and logging."""
    global _flask_app_instance
    _flask_app_instance = app_instance
    set_flask_app_for_command_processor(app_instance)

def log_voice_to_database(user_id, level, message, conversation_id=None, commit=True):
    """
    Logs voice-related events to the database.
    Ensures an application context is available for database operations.
    """
    if _flask_app_instance:
        with _flask_app_instance.app_context():
            try:
                user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
                new_log = Log(
                    user_id=user_id_str,
                    level=level,
                    message=message,
                    conversation_id=conversation_id,
                    source='voice_assistant'
                )
                db.session.add(new_log)
                if commit:
                    db.session.commit()
            except Exception as e:
                logger.error(f"Failed to log voice event to database (within context): {e}")
                logger.error(traceback.format_exc())
                try:
                    if db.session.is_active:
                        db.session.rollback()
                except Exception as rollback_e:
                    logger.error(f"Error during rollback in log_voice_to_database: {rollback_e}")
    else:
        logger.error("Flask app instance not set for log_voice_to_database. Cannot log to DB.")
        logger.error(f"Attempted log message: [{level}] {message}")

ELEVENLABS_CLIENT = None
ELEVENLABS_AVAILABLE = False 

AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "alloy")  # Default voice

user_name_placeholder = "Chirag"

prompt_template = """You are {user_name}'s personal assistant with comprehensive voice command capabilities. Today's schedule: {schedule}

CAPABILITIES:
- Calendar: View schedule, create events, find free time, check next meeting
- Weather: Get current weather for any location
- News: Get latest headlines by category (technology, business, sports, health, etc.)
- Reminders: Set time-based reminders
- Timers: Set countdown timers
- Notes: Take and save notes
- Search: Web search functionality
- Translation: Translate text between languages
- Calculator: Perform mathematical calculations
- Entertainment: Get random facts and jokes

COMMAND EXAMPLES:
- "What's the weather in London?"
- "Tell me the latest technology news"
- "Remind me to call mom in 30 minutes"
- "Set a timer for 5 minutes"
- "Take a note: Buy groceries tomorrow"
- "Calculate 25 times 8"
- "Translate hello to Spanish"
- "Tell me a random fact"
- "Search for Python programming tutorials"

ENHANCED COMMAND PROCESSING:
When users request these actions, respond with the appropriate command format:
- Weather: "I'll get the weather for [location] - weather in [location]"
- News: "Let me get the latest [category] news - news in [category]"
- Reminder: "I'll set a reminder for you - remind me to [task] in [time]"
- Timer: "Setting a timer now - timer for [duration]"
- Note: "I'll save that note - note: [content]"
- Calculator: "Let me calculate that - calculate [expression]"
- Fact: "Here's an interesting fact - random fact"
- Joke: "I'll tell you a joke - tell joke"

CALENDAR MANAGEMENT:
- "Schedule a meeting with John tomorrow at 2pm"
- "What's my schedule today?"
- "When is my next meeting?"
- "Find free time this afternoon"

ENDING CONVERSATION:
When the user says goodbye, wants to end the chat, or says phrases like:
- "That's all", "Thanks, bye", "End chat", "Stop", "Goodbye", "See you later"
Respond with: "Goodbye! Have a great day, {user_name}. CONVERSATION_END"

Keep responses brief and helpful. Always confirm actions before executing commands."""

conversation_active = False
current_user_id = None
current_conversation_id = None

# Simple voice processing implementation using direct API calls
class SimpleVoiceAssistant:
    """Simple voice assistant using direct ElevenLabs API calls"""
    
    def __init__(self, user_id, conversation_id):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.is_listening = False
        
    def speak(self, text):
        """Speak the given text using ElevenLabs TTS"""
        _play_text_via_client(text, self.user_id, self.conversation_id)
        
    def process_voice_input(self, text_input):
        """Process voice input and generate response"""
        try:
            # Log user input
            _log_and_commit(self.user_id, 'USER', f"User said: {text_input}", self.conversation_id)
            
            # Process the command using the existing command processor
            response = self._generate_response(text_input)
            
            # Log agent response
            _log_and_commit(self.user_id, 'AGENT', f"Agent response: {response}", self.conversation_id)
            
            # Speak the response
            self.speak(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing voice input: {e}")
            error_response = "I'm sorry, I encountered an error processing your request."
            self.speak(error_response)
            return error_response
    
    def _generate_response(self, text_input):
        """Generate response based on user input"""
        text_lower = text_input.lower()
        
        # Handle common commands
        if "schedule" in text_lower and ("meeting" in text_lower or "event" in text_lower):
            try:
                from .google_calendar_integration import create_event_from_conversation
                result = create_event_from_conversation(text_input)
                return f"I've created that event for you: {result}"
            except Exception as e:
                return f"I had trouble creating that event: {str(e)}"
                
        elif "weather" in text_lower:
            from .command_processor import VoiceCommandProcessor
            processor = VoiceCommandProcessor(user_id=self.user_id)
            location = "your location"
            if "in" in text_lower:
                location = text_lower.split("in")[-1].strip()
            result = processor.process_command('weather', location=location)
            return result.get('user_message', 'Weather information is not available right now.')
            
        elif "calendar" in text_lower or "schedule" in text_lower:
            try:
                from .google_calendar_integration import get_today_schedule
                schedule = get_today_schedule()
                return f"Here's your schedule: {schedule}"
            except Exception as e:
                return f"I couldn't access your calendar right now: {str(e)}"
                
        elif any(phrase in text_lower for phrase in ["goodbye", "bye", "end chat", "stop", "that's all"]):
            return "Goodbye! Have a great day. CONVERSATION_END"
            
        else:
            # Default helpful response
            return f"I heard you say: {text_input}. I can help you with scheduling events, checking weather, viewing your calendar, and more. What would you like me to do?"

# Global voice assistant instance
current_voice_assistant = None

# Helper to play text using the modern ElevenLabs API
def _play_text_via_client(text_to_speak, user_id, conversation_id):
    global ELEVENLABS_CLIENT, VOICE_ID
    
    if not ELEVENLABS_CLIENT:
        logger.error("ElevenLabs client is not initialized. Cannot play text via ElevenLabs.")
        _log_and_commit(user_id, 'ERROR', "ElevenLabs client not ready for playback.", conversation_id)
        
        # Fallback to pyttsx3 if available
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.say(text_to_speak)
                engine.runAndWait()
                logger.info(f"Played text via pyttsx3 fallback: {text_to_speak}")
                _log_and_commit(user_id, 'INFO', f"Played text via pyttsx3 fallback: {text_to_speak}", conversation_id)
            except Exception as e:
                logger.error(f"Error with pyttsx3 fallback: {e}")
                _log_and_commit(user_id, 'ERROR', f"pyttsx3 fallback failed: {str(e)}", conversation_id)
        return

    try:
        logger.info(f"Attempting to play text via ElevenLabs: {text_to_speak}")
        
        # Use modern ElevenLabs API
        audio_generator = generate(
            text=text_to_speak,
            voice=VOICE_ID,
            model="eleven_multilingual_v2",
            stream=True,
            api_key=API_KEY
        )
        
        # Play the audio stream
        play(audio_generator)
        
        _log_and_commit(user_id, 'INFO', f"Agent spoke via ElevenLabs: {text_to_speak}", conversation_id)
        
    except Exception as e:
        logger.error(f"Error playing text via ElevenLabs: {e}")
        logger.error(traceback.format_exc())
        _log_and_commit(user_id, 'ERROR', f"Failed to speak via ElevenLabs: {str(e)}", conversation_id)
        
        # Fallback to pyttsx3 if available
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.say(text_to_speak)
                engine.runAndWait()
                logger.info(f"Played text via pyttsx3 fallback after ElevenLabs error: {text_to_speak}")
                _log_and_commit(user_id, 'INFO', f"Used pyttsx3 fallback after ElevenLabs error", conversation_id)
            except Exception as fallback_e:
                logger.error(f"Error with pyttsx3 fallback: {fallback_e}")
                _log_and_commit(user_id, 'ERROR', f"Both ElevenLabs and pyttsx3 failed: {str(fallback_e)}", conversation_id)


def _log_and_commit(user_id, level, message, conversation_id):
    """Helper to log and commit within an app context."""
    log_voice_to_database(user_id, level, message, conversation_id=conversation_id)

def process_voice_command(text_input):
    """Process voice command with the simple voice assistant"""
    global current_voice_assistant, conversation_active, current_user_id, current_conversation_id
    
    if not current_voice_assistant:
        logger.error("Voice assistant not active")
        return "Voice assistant is not active"
    
    try:
        response = current_voice_assistant.process_voice_input(text_input)
        
        if "CONVERSATION_END" in response:
            logger.info("Ending conversation as requested...")
            _log_and_commit(current_user_id, 'INFO', "Voice conversation ended by user request", current_conversation_id)
            conversation_active = False
            current_voice_assistant = None
            
        return response
        
    except Exception as e:
        logger.error(f"Error processing voice command: {e}")
        logger.error(traceback.format_exc())
        return f"I encountered an error: {str(e)}"

def auto_shutdown_timer():
    global conversation_active, current_voice_assistant, current_user_id, current_conversation_id
    time.sleep(600)  # 10 minutes
    if conversation_active:
        logger.info("Auto-shutdown: Ending conversation due to inactivity...")
        _log_and_commit(current_user_id, 'INFO', "Voice conversation ended due to inactivity (10 min timeout)", current_conversation_id)
        conversation_active = False
        current_voice_assistant = None

def _start_voice_assistant_internal(user_id: uuid.UUID):
    """
    Internal function to start the simplified voice assistant.
    Assumes an app context is already pushed.
    """
    global conversation_active, current_voice_assistant, current_user_id, current_conversation_id, ELEVENLABS_CLIENT, ELEVENLABS_AVAILABLE
    
    current_user_id = user_id
    conversation_active = True
    
    ELEVENLABS_CLIENT = None
    ELEVENLABS_AVAILABLE = False

    # Check if ElevenLabs core imports were successful
    if not ELEVENLABS_IMPORTS_SUCCESS:
        error_msg = "ElevenLabs modules failed to import at startup. Voice functionality is disabled."
        _log_and_commit(current_user_id, 'CRITICAL', error_msg, current_conversation_id)
        raise ImportError(error_msg)

    try:
        # Get user information
        user = User.query.get(user_id)
        user_name = user.get_full_name() if user and user.get_full_name() else user_name_placeholder

        # Create database conversation record
        session_id = str(uuid.uuid4())
        new_db_conversation = DBConversation(user_id=user_id, session_id=session_id)
        db.session.add(new_db_conversation)
        db.session.commit()
        current_conversation_id = new_db_conversation.id

        # Initialize ElevenLabs client
        try:
            if API_KEY and API_KEY != "your_elevenlabs_api_key_here":
                # For the simplified version, we'll use the global functions
                ELEVENLABS_AVAILABLE = True
                logger.info("ElevenLabs API key found, voice synthesis available.")
            else:
                logger.warning("ElevenLabs API key is not set. Using text-only mode.")
                ELEVENLABS_AVAILABLE = False
        except Exception as e:
            logger.error(f"Error setting up ElevenLabs: {e}")
            ELEVENLABS_AVAILABLE = False

        # Create voice assistant instance
        current_voice_assistant = SimpleVoiceAssistant(user_id, current_conversation_id)
        
        logger.info("Starting simplified voice assistant...")
        _log_and_commit(current_user_id, 'INFO', "Voice assistant session starting", current_conversation_id)
        
        # Initial greeting
        initial_greeting = f"Hello {user_name}! I'm your voice assistant. I can help you with calendar events, weather, and more. What can I do for you?"
        current_voice_assistant.speak(initial_greeting)

        # Start auto-shutdown timer
        timer_thread = threading.Thread(target=auto_shutdown_timer, daemon=True)
        timer_thread.start()
        
        _log_and_commit(current_user_id, 'INFO', "Voice assistant session initialized successfully", current_conversation_id)
        
        # Keep the session alive
        while conversation_active:
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected. Ending conversation...")
        _log_and_commit(current_user_id, 'INFO', "Voice conversation interrupted by keyboard", current_conversation_id)
        conversation_active = False
    except Exception as e:
        logger.error(f"Error starting voice assistant: {e}")
        logger.error(traceback.format_exc())
        _log_and_commit(current_user_id, 'ERROR', f"Voice assistant error: {str(e)}", current_conversation_id)
        conversation_active = False
        raise
    finally:
        if _flask_app_instance:
            try:
                db.session.remove()
                logger.info("Database session removed in finally block.")
            except Exception as cleanup_e:
                logger.error(f"Error cleaning up database session in finally block: {cleanup_e}")

def start_voice_assistant(user_id: uuid.UUID, app_instance: Flask, retries: int = 3, delay: int = 5):
    """
    Public function to start the voice assistant with retry logic.
    Ensures the Flask app context is pushed for the internal function.
    """
    global _flask_app_instance
    set_flask_app(app_instance)

    for attempt in range(retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{retries} to start voice assistant for user {user_id}")
            with app_instance.app_context():
                _start_voice_assistant_internal(user_id)
            logger.info("Voice assistant started successfully.")
            return
        except Exception as e:
            logger.error(f"Failed to start voice assistant on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"All {retries} attempts failed to start voice assistant for user {user_id}.")
                log_voice_to_database(user_id, 'CRITICAL', f"Voice assistant failed to start after {retries} attempts: {str(e)}", conversation_id=None)
                raise
