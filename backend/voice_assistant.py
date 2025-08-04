# backend/voice_assistant.py
import os
import logging
import threading
import time
import queue
from typing import Optional, Callable
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
import requests
import uuid
import traceback
import pyttsx3

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
ELEVENLABS_CLIENT = None
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

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
        self.user_transcript_queue = queue.Queue() # Queue is now an instance attribute

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

    def _get_elevenlabs_client(self):
        """Initializes and returns a single ElevenLabs client instance."""
        global ELEVENLABS_CLIENT
        if ELEVENLABS_CLIENT is None:
            if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY == "your_elevenlabs_api_key_here":
                raise ValueError("ElevenLabs API key is not set or is a placeholder in .env.")
            try:
                ELEVENLABS_CLIENT = ElevenLabs(api_key=ELEVENLABS_API_KEY)
                logger.info("ElevenLabs client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs client: {e}")
                raise
        return ELEVENLABS_CLIENT

    def _play_text_via_stream(self, text_to_speak, voice="alloy"):
        """Generates and streams audio to the user with error handling."""
        try:
            client = self._get_elevenlabs_client()
            audio_stream = client.generate(
                text=text_to_speak,
                voice=voice,
                model="eleven_turbo_v2",
                stream=True
            )
            stream(audio_stream)
            self._log_to_frontend(f"Agent spoke: {text_to_speak[:50]}...", 'info')
            self._log_to_database(self.user_id, 'INFO', f"Agent spoke: {text_to_speak[:50]}...", self.conversation_id)
        except requests.exceptions.RequestException as e:
            logger.error(f"ElevenLabs network error: {e}")
            self._log_to_frontend(f"Network error with ElevenLabs API: {e}", 'error')
            self._play_text_via_pyttsx3(text_to_speak)
        except Exception as e:
            logger.error(f"Error playing text via ElevenLabs stream: {e}")
            logger.error(traceback.format_exc())
            self._log_to_frontend("An error occurred while speaking.", 'error')
            self._play_text_via_pyttsx3(text_to_speak)

    def _play_text_via_pyttsx3(self, text):
        """Fallback TTS using pyttsx3."""
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            logger.info("Used pyttsx3 fallback.")
        except Exception as e:
            logger.error(f"pyttsx3 fallback failed: {e}")

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

        # ... (rest of your command processing logic) ...

        if "CONVERSATION_END" in response_text:
            self._play_text_via_stream(f"Goodbye, {user_name}!")
            conversation_active = False
            self._log_to_database(user_id, 'INFO', "Voice conversation ended by agent.", self.conversation_id)
            return

        with _flask_app_instance.app_context():
            user = User.query.get(user_id)
            preferred_voice = user.preferred_voice if user else "alloy"

        if command_executed_message:
            self._play_text_via_stream(command_executed_message, voice=preferred_voice)
        else:
            self._play_text_via_stream(response_text, voice=preferred_voice)

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
        self._play_text_via_stream(initial_greeting, voice=preferred_voice)

        while self.is_listening:
            try:
                transcript = self.user_transcript_queue.get(timeout=1)
                
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
                self._play_text_via_stream("Sorry, an internal error occurred. The conversation will now end.")
                self.stop_listening()

        self._log_to_frontend("Voice assistant session ended.", 'info')
        self._log_to_database(self.user_id, 'INFO', "Voice assistant session ended.", self.conversation_id)

    def start_listening(self, user_id):
        """Starts the voice assistant in a separate thread."""
        if self.is_listening:
            return False, "Voice assistant is already active for this user."

        self.user_id = user_id
        self.is_listening = True
        self.status = "Listening"
        self._log_to_frontend("Starting voice assistant...", 'info')

        with _flask_app_instance.app_context():
            user = User.query.get(self.user_id)
            session_id = str(uuid.uuid4())
            new_db_conversation = DBConversation(user_id=self.user_id, session_id=session_id)
            db.session.add(new_db_conversation)
            db.session.commit()
            self.conversation_id = new_db_conversation.id

        self.listening_thread = threading.Thread(target=self._listening_loop, daemon=True)
        self.listening_thread.start()
        
        return True, "Voice assistant started successfully."

    def stop_listening(self):
        """Stops the voice assistant."""
        if not self.is_listening:
            return False, "Voice assistant is not active."
        
        self.is_listening = False
        self.status = "Inactive"
        self._log_to_frontend("Voice assistant stopped.", 'info')
        return True, "Voice assistant stopped successfully."

    def get_status(self):
        """Returns the current status of the voice assistant."""
        return {
            "status": self.status,
            "is_listening": self.is_listening,
            "user_id": str(self.user_id) if self.user_id else None
        }

