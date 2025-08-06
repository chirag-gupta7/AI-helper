# backend/voice_assistant.py
import os
import logging
import threading
import time
import queue
import uuid
import traceback
from typing import Optional, Callable
from flask import Flask

# Import for ElevenLabs SDK with modern API
try:
    from elevenlabs import generate, play, set_api_key
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logging.warning("ElevenLabs not found. TTS functionality will be limited to pyttsx3 fallback.")

# Attempt to import pyttsx3 for fallback audio, if available
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logging.warning("pyttsx3 not found. Local TTS fallback will not be available.")

from .memory import ConversationMemory, ConversationContext

# Core modules from your project for data handling and commands
from .models import Conversation as DBConversation, Message, MessageType, db, User, Log
from .command_processor import VoiceCommandProcessor, set_flask_app_for_command_processor
from .google_calendar_integration import (
    get_today_schedule,
    create_event_from_conversation,
    get_upcoming_events,
    get_next_meeting,
    get_free_time_today
)

# Set up logging for this module
logger = logging.getLogger(__name__)

# Global variables for Flask app context and callbacks
_flask_app_instance = None
_on_status_change: Optional[Callable] = None
_on_log: Optional[Callable] = None
_on_log_to_db: Optional[Callable] = None

# Global state for the voice assistant thread
conversation_active = False
current_user_id = None
current_conversation_id = None

# ElevenLabs API setup
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

# Modern ElevenLabs speech generation function
def generate_speech(text: str, voice_id: str = None) -> bool:
    """Generate and play speech using modern ElevenLabs API with pyttsx3 fallback"""
    try:
        if ELEVENLABS_AVAILABLE and API_KEY and API_KEY != "your_elevenlabs_api_key_here":
            voice = voice_id or VOICE_ID
            audio = generate(
                text=text,
                voice=voice,
                model="eleven_monolingual_v1"
            )
            play(audio)
            logger.info(f"Successfully played text via ElevenLabs: {text[:50]}...")
            return True
    except Exception as e:
        logger.error(f"ElevenLabs TTS failed: {e}")
        # Fallback to pyttsx3
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                logger.info(f"Successfully played text via pyttsx3 fallback: {text[:50]}...")
                return True
            except Exception as fallback_e:
                logger.error(f"pyttsx3 fallback also failed: {fallback_e}")
    
    logger.error("All TTS methods failed")
    return False

# Simple voice processing implementation using direct API calls
class SimpleVoiceAssistant:
    """Simple voice assistant using modern ElevenLabs API"""

    def __init__(self, user_id, conversation_id):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.is_listening = False

    def speak(self, text):
        """Speak the given text using modern ElevenLabs TTS"""
        success = generate_speech(text)
        if success:
            _log_and_commit(self.user_id, 'INFO', f"Agent spoke: {text[:50]}...", self.conversation_id)
        else:
            _log_and_commit(self.user_id, 'ERROR', f"Failed to speak: {text[:50]}...", self.conversation_id)

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
                result = create_event_from_conversation(text_input)
                return f"I've created that event for you: {result}"
            except Exception as e:
                return f"I had trouble creating that event: {str(e)}"

        elif "weather" in text_lower:
            processor = VoiceCommandProcessor(user_id=self.user_id)
            location = "your location"
            if "in" in text_lower:
                location = text_lower.split("in")[-1].strip()
            result = processor.process_command('weather', location=location)
            return result.get('user_message', 'Weather information is not available right now.')

        elif "calendar" in text_lower or "schedule" in text_lower:
            try:
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

def log_voice_to_database(user_id, level, message, conversation_id):
    """
    A standalone function to log to the database using the global callback.
    This resolves the 'log_voice_to_database' undefined variable errors.
    """
    if _on_log_to_db:
        _on_log_to_db(user_id, level, message, conversation_id)

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
    global conversation_active, current_voice_assistant, current_user_id, current_conversation_id

    current_user_id = user_id
    conversation_active = True

    # Check if ElevenLabs core imports were successful
    if not ELEVENLABS_AVAILABLE:
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

        # Initialize ElevenLabs
        try:
            if API_KEY and API_KEY != "your_elevenlabs_api_key_here":
                set_api_key(API_KEY)
                logger.info("ElevenLabs API key found, voice synthesis available.")
            else:
                logger.warning("ElevenLabs API key is not set. Using text-only mode.")
        except Exception as e:
            logger.error(f"Error setting up ElevenLabs: {e}")

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
    _flask_app_instance = app_instance
    set_flask_app_for_command_processor(app_instance)

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
                logger.error(f"Error in frontend log callback: {e}")

    def _log_to_database(self, user_id, level, message, conversation_id=None):
        """Logs voice-related events to the database using the callback."""
        if _on_log_to_db:
            _on_log_to_db(user_id, level, message, conversation_id)

    def _play_text_via_modern_api(self, text_to_speak, voice=None):
        """Generates and plays audio using the modern ElevenLabs API."""
        try:
            voice_id = voice or VOICE_ID
            logger.info(f"Playing text via modern ElevenLabs API: {text_to_speak[:50]}...")
            
            success = generate_speech(text_to_speak, voice_id)
            
            if success:
                self._log_to_frontend(f"Agent spoke: {text_to_speak[:50]}...", 'info')
                self._log_to_database(self.user_id, 'INFO', f"Agent spoke: {text_to_speak[:50]}...", self.conversation_id)
            else:
                self._log_to_frontend("Failed to generate speech", 'error')
                self._log_to_database(self.user_id, 'ERROR', "Speech generation failed", self.conversation_id)
            
        except Exception as e:
            logger.error(f"Error in modern ElevenLabs API: {e}")
            logger.error(traceback.format_exc())
            self._log_to_frontend("An error occurred while speaking.", 'error')

    def _process_llm_response(self, response_text, user_id, user_name):
        """Processes an agent's text response, executes commands, and plays audio."""
        global conversation_active

        self._log_to_frontend(f"Agent: {response_text}", 'info')
        self._log_to_database(user_id, 'AGENT', response_text, self.conversation_id)

        command_processor = VoiceCommandProcessor(user_id=user_id)
        command_executed_message = None

        response_lower = response_text.lower()

        # --- Command Processing Logic ---
        if "i'll create that event for you:" in response_lower:
            event_description = response_text.split("i'll create that event for you:")[1].strip()
            try:
                result = create_event_from_conversation(event_description)
                command_executed_message = result
            except Exception as e:
                command_executed_message = f"❌ Error creating event: {e}"
                self._log_to_frontend(f"Error executing command: {command_executed_message}", 'error')

        elif "weather in" in response_lower:
            try:
                location = response_lower.split("weather in")[1].strip().replace("?", "").replace(".", "")
                result = command_processor.process_command('weather', location=location)
                command_executed_message = result.get('user_message', 'Error fetching weather.')
                self._log_to_frontend(f"Command result: {command_executed_message}", 'info')
            except Exception as e:
                command_executed_message = f"Sorry, I couldn't get the weather right now: {e}"
                self._log_to_frontend(f"Error executing command: {command_executed_message}", 'error')

        if "CONVERSATION_END" in response_text:
            self._play_text_via_modern_api(f"Goodbye, {user_name}!")
            conversation_active = False
            self._log_to_database(user_id, 'INFO', "Voice conversation ended by agent.", self.conversation_id)
            return

        with _flask_app_instance.app_context():
            user = User.query.get(user_id)
            preferred_voice = user.preferred_voice if user else "alloy"

        if command_executed_message:
            self._play_text_via_modern_api(command_executed_message, voice=preferred_voice)
        else:
            self._play_text_via_modern_api(response_text, voice=preferred_voice)

    def _simulate_llm_response(self, transcript):
        """Simulates a dynamic LLM response based on the transcript."""
        transcript_lower = transcript.lower()

        if "schedule" in transcript_lower and "meeting" in transcript_lower:
            return f"I'll create that event for you: {transcript}"
        if "today's schedule" in transcript_lower or "my schedule today" in transcript_lower:
            return "I can get your schedule for today."
        if "next meeting" in transcript_lower:
            return "Let me check for your next meeting."
        if "free time" in transcript_lower:
            return "I can find your free time today."
        if "weather" in transcript_lower:
            return f"I'll get the weather for [location] - weather in London"
        if "news" in transcript_lower:
            return "I can get the latest news for you."
        if "remind me to" in transcript_lower:
            return "I can set a reminder for you."
        if "timer for" in transcript_lower:
            return "I can set a timer for you."

        if "goodbye" in transcript_lower or "end chat" in transcript_lower:
            return "Goodbye! Have a great day, Chirag. CONVERSATION_END"

        return "I'm not sure how to respond to that. You can ask about your schedule, weather, or news."

    def _listening_loop(self):
        """The main listening and processing loop."""
        global conversation_active

        with _flask_app_instance.app_context():
            user = User.query.get(self.user_id)
            user_name = user.username if user else "Chirag"
            preferred_voice = user.preferred_voice if user else "alloy"

        self._log_to_frontend("Voice assistant session started.", 'success')
        self._log_to_frontend("Listening for commands...", 'status')

        initial_greeting = f"How can I help you?"
        self._play_text_via_modern_api(initial_greeting, voice=preferred_voice)

        while self.is_listening:
            try:
                transcript = self.user_transcript_queue.get(timeout=1)
                
                # Check for shutdown signal
                if transcript == "SHUTDOWN_SIGNAL":
                    self._log_to_frontend("Shutting down voice assistant...", 'status')
                    self.status = "Inactive"
                    break

                self._log_to_frontend(f"User: {transcript}", 'info')
                self._log_to_database(self.user_id, 'USER', transcript, self.conversation_id)

                response_text = self._simulate_llm_response(transcript)
                self._process_llm_response(response_text, self.user_id, user_name)

            except queue.Empty:
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in listening loop: {e}")
                logger.error(traceback.format_exc())
                self._log_to_frontend("An unexpected error occurred.", 'error')

        self._log_to_frontend("Voice assistant session ended.", 'info')
        self._log_to_database(self.user_id, 'INFO', "Voice assistant session ended.", self.conversation_id)

    def start_listening(self, user_id):
        """Starts the voice assistant in a separate thread."""
        if self.is_listening:
            return False, "Voice assistant is already listening"

        self.user_id = user_id
        self.is_listening = True
        self.status = "Listening"
        self._log_to_frontend("Starting voice assistant...", 'info')

        with _flask_app_instance.app_context():
            session_id = str(uuid.uuid4())
            new_db_conversation = DBConversation(user_id=user_id, session_id=session_id)
            db.session.add(new_db_conversation)
            db.session.commit()
            self.conversation_id = new_db_conversation.id

        self.listening_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listening_thread.start()

        return True, "Voice assistant started successfully"

    def stop_listening(self):
        """Stops the voice assistant."""
        if not self.is_listening:
            return False, "Voice assistant is not currently active"

        self.is_listening = False
        self.status = "Inactive"
        self._log_to_frontend("Voice assistant stopped.", 'info')
        
        # Add shutdown signal to queue
        try:
            self.user_transcript_queue.put("SHUTDOWN_SIGNAL")
        except:
            pass
            
        return True, "Voice assistant stopped"

    def get_status(self):
        """Returns the current status of the voice assistant."""
        return {
            'active': self.is_listening,
            'status': self.status,
            'user_id': str(self.user_id) if self.user_id else None,
            'is_listening': self.is_listening
        }