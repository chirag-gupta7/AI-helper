# backend/voice_assistant.py
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
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
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
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "echo")

# Configure ElevenLabs API
if ELEVENLABS_AVAILABLE and API_KEY:
    try:
        set_api_key(API_KEY)
        logger.info("ElevenLabs API key configured successfully")
    except Exception as e:
        logger.error(f"Error configuring ElevenLabs API key: {e}")

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

# Global variables for Flask app context and callbacks
_flask_app_instance = None
_on_status_change: Optional[Callable] = None
_on_log: Optional[Callable] = None
_on_log_to_db: Optional[Callable] = None

# Global state for the voice assistant thread
conversation_active = False
current_user_id = None
current_conversation_id = None

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

def generate_speech(text: str, voice_id: str = None) -> bool:
    """Generate and play speech using modern ElevenLabs API with pyttsx3 fallback"""
    try:
        # Try ElevenLabs first
        if ELEVENLABS_AVAILABLE and API_KEY:
            voice = voice_id or VOICE_ID
            try:
                logger.info(f"Attempting to use ElevenLabs with voice: {voice}")
                audio = generate(
                    text=text,
                    voice=voice,
                    model="eleven_monolingual_v1"
                )
                play(audio)
                logger.info(f"Successfully played text via ElevenLabs: {text[:50]}...")
                return True
            except Exception as e:
                logger.error(f"ElevenLabs TTS error: {e}")
                logger.error(traceback.format_exc())
                logger.warning("Falling back to pyttsx3")
        else:
            logger.warning("ElevenLabs not available or API key not set")
            
        # Fall back to pyttsx3
        if PYTTSX3_AVAILABLE:
            try:
                logger.info("Attempting to use pyttsx3 fallback")
                engine = pyttsx3.init()
                
                # Set properties for better compatibility
                engine.setProperty('rate', 150)
                engine.setProperty('volume', 0.9)
                
                # Get available voices and select one
                voices = engine.getProperty('voices')
                if voices:
                    engine.setProperty('voice', voices[0].id)  # Use first available voice
                
                engine.say(text)
                engine.runAndWait()
                logger.info(f"Successfully played text via pyttsx3 fallback: {text[:50]}...")
                return True
            except Exception as fallback_e:
                logger.error(f"pyttsx3 fallback failed with error: {fallback_e}")
                logger.error(traceback.format_exc())
                
                # Even if both TTS methods fail, log the response as text
                logger.info(f"Text response (no audio): {text}")
                return False
        else:
            logger.error("No TTS methods available")
            return False
            
    except Exception as e:
        logger.error(f"Catastrophic error in speech generation: {e}")
        logger.error(traceback.format_exc())
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
        """Process voice input from the user."""
        if not text_input or not isinstance(text_input, str):
            self._log_to_frontend("Received empty or invalid input", 'warning')
            return
        
        # Log the input
        self._log_to_frontend(f"User: {text_input}", 'info')
        self._log_to_database(self.user_id, 'USER', text_input, self.conversation_id)
        
        try:
            # Add to transcript queue for processing
            self.user_transcript_queue.put(text_input)
            self._log_to_frontend(f"Added to processing queue: {text_input}", 'debug')
        except Exception as e:
            self._log_to_frontend(f"Error queuing input: {str(e)}", 'error')
            logger.error(f"Error queuing voice input: {str(e)}")
            logger.error(traceback.format_exc())

    def _process_input_with_agent(self, text_input, user_name):
        """Process input and generate a response using the agent logic."""
        # Use the existing _simulate_llm_response method for now
        return self._simulate_llm_response(text_input)

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
                # Use the callback directly without broadcast parameter
                _on_log(message, level)
            except Exception as e:
                logger.error(f"Error in frontend log callback: {str(e)}")
                # Try alternative approach if the first one fails
                try:
                    socketio = _flask_app_instance.extensions['socketio']
                    socketio.emit('log', {'message': message, 'level': level}, namespace='/')
                except Exception as e2:
                    logger.error(f"Failed to emit log event: {str(e2)}")

    def _log_to_database(self, user_id, level, message, conversation_id=None):
        """Logs voice-related events to the database using the callback."""
        if _on_log_to_db:
            _on_log_to_db(user_id, level, message, conversation_id)

    # In VoiceAssistant class, modify the _play_text_via_modern_api method
    def _play_text_via_modern_api(self, text_to_speak, voice=None):
        """Generates and plays audio using the modern ElevenLabs API."""
        try:
            voice_id = voice or VOICE_ID
            logger.info(f"Playing text via modern ElevenLabs API: {text_to_speak[:50]}...")
            
            success = generate_speech(text_to_speak, voice_id)
            
            # Always log the text response to the frontend and database
            self._log_to_frontend(f"Agent: {text_to_speak}", 'info')
            self._log_to_database(self.user_id, 'INFO', f"Agent response: {text_to_speak}", self.conversation_id)
            
            # Even if speech fails, we've logged the text response
            if not success:
                self._log_to_frontend("Failed to generate speech, continuing in text-only mode", 'warning')
                self._log_to_database(self.user_id, 'WARNING', "Speech generation failed, using text-only mode", self.conversation_id)
            
        except Exception as e:
            logger.error(f"Error in modern ElevenLabs API: {e}")
            logger.error(traceback.format_exc())
            self._log_to_frontend(f"Speech failed, but response is: {text_to_speak[:100]}...", 'warning')

    def _process_llm_response(self, response_text, user_id, user_name):
        """Processes an agent's text response, executes commands, and plays audio."""
        global conversation_active

        self._log_to_frontend(f"Agent: {response_text}", 'info')
        self._log_to_database(user_id, 'AGENT', response_text, self.conversation_id)

        command_processor = VoiceCommandProcessor(user_id=user_id)
        command_executed_message = None

        response_lower = response_text.lower()

        # --- Command Processing Logic ---
        # Safer string parsing with error handling
        try:
            if "i'll create that event for you:" in response_lower:
                # Use safer split that won't fail if the pattern isn't found correctly
                parts = response_text.split("i'll create that event for you:")
                if len(parts) > 1:
                    event_description = parts[1].strip()
                    try:
                        result = create_event_from_conversation(event_description)
                        command_executed_message = result
                    except Exception as e:
                        command_executed_message = f"❌ Error creating event: {e}"
                        self._log_to_frontend(f"Error executing command: {command_executed_message}", 'error')
                else:
                    self._log_to_frontend("Could not parse event details from response", 'warning')
            
            elif "weather in" in response_lower:
                try:
                    # Safer parsing that won't cause index errors
                    parts = response_lower.split("weather in")
                    if len(parts) > 1:
                        location = parts[1].strip().replace("?", "").replace(".", "")
                        result = command_processor.process_command('weather', location=location)
                        command_executed_message = result.get('user_message', 'Error fetching weather.')
                        self._log_to_frontend(f"Command result: {command_executed_message}", 'info')
                    else:
                        self._log_to_frontend("Could not parse location from weather request", 'warning')
                except Exception as e:
                    command_executed_message = f"Sorry, I couldn't get the weather right now: {e}"
                    self._log_to_frontend(f"Error executing command: {command_executed_message}", 'error')
        
        except Exception as e:
            self._log_to_frontend(f"Error processing response: {str(e)}", 'error')
            logger.error(f"Error processing LLM response: {str(e)}")
            logger.error(traceback.format_exc())
            command_executed_message = "I encountered an error processing your request."

        if "CONVERSATION_END" in response_text:
            self._play_text_via_modern_api(f"Goodbye, {user_name}!")
            conversation_active = False
            self._log_to_database(user_id, 'INFO', "Voice conversation ended by agent.", self.conversation_id)
            return

        try:
            with _flask_app_instance.app_context():
                user = User.query.get(user_id)
                preferred_voice = user.preferred_voice if user and hasattr(user, 'preferred_voice') else "alloy"

            if command_executed_message:
                self._play_text_via_modern_api(command_executed_message, voice=preferred_voice)
            else:
                self._play_text_via_modern_api(response_text, voice=preferred_voice)
        except Exception as e:
            self._log_to_frontend(f"Error playing speech: {str(e)}", 'error')
            logger.error(f"Error playing speech: {str(e)}")

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