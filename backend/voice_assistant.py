import os
from dotenv import load_dotenv
import logging # Ensure logging is imported here
import threading
import time
from flask import Flask # Import Flask for type hinting
import uuid
import traceback

# Import for ElevenLabs SDK version check
try:
    import elevenlabs
    from packaging import version
    # Check minimum required ElevenLabs SDK version
    if version.parse(elevenlabs.__version__) < version.parse("2.7.1"):
        raise ImportError(f"ElevenLabs SDK version {elevenlabs.__version__} is too old. >=2.7.1 is required.")
    
    # Attempt to import core ElevenLabs classes globally
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation
    from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
    from elevenlabs.types import ConversationConfig
    ELEVENLABS_IMPORTS_SUCCESS = True
    # logger.info(f"ElevenLabs SDK version {elevenlabs.__version__} loaded successfully.") # Moved this line below logger definition

except ImportError as e:
    ELEVENLABS_IMPORTS_SUCCESS = False
    logging.error(f"CRITICAL: ElevenLabs core imports or version check failed: {e}. Voice functionality will be disabled.")
    logging.error(traceback.format_exc())
except Exception as e: # Catch any other unexpected errors during initial imports
    ELEVENLABS_IMPORTS_SUCCESS = False
    logging.error(f"CRITICAL: Unexpected error during ElevenLabs initial setup: {e}. Voice functionality will be disabled.")
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
ELEVENLABS_AVAILABLE = False # This flag now depends on ELEVENLABS_IMPORTS_SUCCESS and client init

AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
API_KEY = os.getenv("ELEVENLABS_API_KEY")

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
conversation_instance = None
current_user_id = None
current_conversation_id = None

# Helper to play text using the ElevenLabs client directly
def _play_text_via_client(text_to_speak, user_id, conversation_id):
    global ELEVENLABS_CLIENT, conversation_instance
    
    # Detailed logging for debugging ELEVENLABS_CLIENT
    logger.debug(f"_play_text_via_client: ELEVENLABS_CLIENT type: {type(ELEVENLABS_CLIENT)}")
    if ELEVENLABS_CLIENT:
        logger.debug(f"_play_text_via_client: ELEVENLABS_CLIENT attributes: {dir(ELEVENLABS_CLIENT)}")

    if not ELEVENLABS_CLIENT or not hasattr(ELEVENLABS_CLIENT, 'generate'):
        logger.error("ElevenLabs client is not initialized or does not have a 'generate' method. Cannot play text via ElevenLabs.")
        _log_and_commit(user_id, 'ERROR', "ElevenLabs client not ready for playback.", conversation_id)
        
        # Fallback to pyttsx3 if available for debugging audio output
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.say(f"ElevenLabs audio failed. {text_to_speak}")
                engine.runAndWait()
                logger.info(f"Played text via pyttsx3 fallback: {text_to_speak}")
                _log_and_commit(user_id, 'INFO', f"Played text via pyttsx3 fallback: {text_to_speak}", conversation_id)
            except Exception as e:
                logger.error(f"Error with pyttsx3 fallback: {e}")
                _log_and_commit(user_id, 'ERROR', f"pyttsx3 fallback failed: {str(e)}", conversation_id)
        return

    if not conversation_instance or not hasattr(conversation_instance, 'audio_interface') or not conversation_instance.audio_interface:
        logger.warning("Conversation instance or audio interface not available for direct text playback (ElevenLabs).")
        _log_and_commit(user_id, 'WARNING', "Could not play text directly (audio_interface missing).", conversation_id)
        return

    try:
        logger.info(f"Attempting to play text via ElevenLabs client: {text_to_speak}")
        audio_stream = ELEVENLABS_CLIENT.generate(
            text=text_to_speak,
            voice="alloy", # Default voice
            model="eleven_turbo_v2", # Default model
            stream=True
        )
        conversation_instance.audio_interface.play(audio_stream)
        _log_and_commit(user_id, 'INFO', f"Agent spoke via ElevenLabs client: {text_to_speak}", conversation_id)
    except Exception as e:
        logger.error(f"Error playing text via ElevenLabs client (general exception): {e}")
        logger.error(traceback.format_exc())
        _log_and_commit(user_id, 'ERROR', f"Failed to speak via ElevenLabs client: {str(e)}", conversation_id)


def _log_and_commit(user_id, level, message, conversation_id):
    """Helper to log and commit within an app context."""
    log_voice_to_database(user_id, level, message, conversation_id=conversation_id)

def print_agent_response(response):
    global conversation_active, conversation_instance, current_user_id, current_conversation_id
    logger.info(f"Agent: {response}")
    
    _log_and_commit(current_user_id, 'AGENT', f"Agent response: {response}", current_conversation_id)
    
    command_processor = VoiceCommandProcessor(user_id=current_user_id)
    command_executed_message = None # To store the message from executed command

    response_lower = response.lower()
    
    # --- Command Processing Logic ---
    # For each command, try to extract parameters and execute.
    # If successful, store the 'user_message' from the command_processor result.

    if "i'll create that event for you:" in response_lower:
        event_description = response.split("I'll create that event for you:")[1].strip()
        logger.info(f"Creating calendar event: {event_description}")
        _log_and_commit(current_user_id, 'INFO', f"Voice assistant creating calendar event: {event_description}", current_conversation_id)
        try:
            result = create_event_from_conversation(event_description)
            logger.info(f"Calendar result: {result}")
            _log_and_commit(current_user_id, 'INFO', f"Calendar event created successfully: {event_description} - Result: {result}", current_conversation_id)
            command_executed_message = result # Calendar functions already return user-friendly strings
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            _log_and_commit(current_user_id, 'ERROR', f"Failed to create calendar event '{event_description}': {str(e)}", current_conversation_id)
            command_executed_message = f"❌ Error creating event: {e}"

    elif "weather in" in response_lower:
        try:
            location = response_lower.split("weather in")[1].strip().replace("?", "").replace(".", "")
            result = command_processor.process_command('weather', location=location)
            logger.info(f"Weather command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing weather command: {e}")
            command_executed_message = f"Sorry, I couldn't get the weather right now: {e}"

    elif "news in" in response_lower:
        try:
            category = response_lower.split("news in")[1].strip().replace(".", "").replace("news", "").strip()
            result = command_processor.process_command('news', category=category)
            logger.info(f"News command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing news command: {e}")
            command_executed_message = f"Sorry, I couldn't get the news right now: {e}"

    elif "remind me to" in response_lower:
        try:
            parts = response_lower.split("remind me to")[1].strip().split(" in ")
            reminder_text = parts[0].strip()
            time_str = parts[1] if len(parts) > 1 else "15 minutes"
            
            remind_in_minutes = 15
            if "minute" in time_str:
                minutes = ''.join(filter(str.isdigit, time_str.split("minute")[0]))
                if minutes:
                    remind_in_minutes = int(minutes)
            elif "hour" in time_str:
                hours = ''.join(filter(str.isdigit, time_str.split("hour")[0]))
                if hours:
                    remind_in_minutes = int(hours) * 60
            
            result = command_processor.process_command('reminder', reminder_text=reminder_text, remind_in_minutes=remind_in_minutes)
            logger.info(f"Reminder command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing reminder command: {e}")
            command_executed_message = f"Sorry, I couldn't set that reminder: {e}"

    elif "timer for" in response_lower:
        try:
            duration_str = response_lower.split("timer for")[1].strip()
            timer_name = "Timer"
            
            duration_seconds = 300
            if "minute" in duration_str:
                minutes = ''.join(filter(str.isdigit, duration_str.split("minute")[0]))
                if minutes:
                    duration_seconds = int(minutes) * 60
            elif "second" in duration_str:
                seconds = ''.join(filter(str.isdigit, duration_str.split("second")[0]))
                if seconds:
                    duration_seconds = int(seconds)
            elif "hour" in duration_str:
                hours = ''.join(filter(str.isdigit, duration_str.split("hour")[0]))
                if hours:
                    duration_seconds = int(hours) * 3600
            
            result = command_processor.process_command('timer', duration_seconds=duration_seconds, timer_name=timer_name)
            logger.info(f"Timer command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing timer command: {e}")
            command_executed_message = f"Sorry, I couldn't set that timer: {e}"

    elif "note:" in response_lower:
        try:
            note_text = response.split(":", 1)[1].strip()
            result = command_processor.process_command('note', note_text=note_text)
            logger.info(f"Note command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing note command: {e}")
            command_executed_message = f"Sorry, I couldn't save that note: {e}"

    elif "calculate" in response_lower:
        try:
            expression = response_lower.split("calculate")[1].strip()
            expression = expression.replace("that", "").replace("this", "").strip()
            result = command_processor.process_command('calculate', expression=expression)
            logger.info(f"Calculator command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing calculator command: {e}")
            command_executed_message = f"Sorry, I couldn't calculate that: {e}"

    elif "random fact" in response_lower or "interesting fact" in response_lower:
        try:
            result = command_processor.process_command('fact')
            logger.info(f"Fact command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing fact command: {e}")
            command_executed_message = f"Sorry, I couldn't get a fact right now: {e}"

    elif "tell joke" in response_lower or "tell me a joke" in response_lower:
        try:
            result = command_processor.process_command('joke')
            logger.info(f"Joke command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing joke command: {e}")
            command_executed_message = f"Sorry, I couldn't tell a joke right now: {e}"

    elif "search for" in response_lower:
        try:
            query = response_lower.split("search for")[1].strip()
            result = command_processor.process_command('search', query=query)
            logger.info(f"Search command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing search command: {e}")
            command_executed_message = f"Sorry, I couldn't perform that search: {e}"

    elif "translate" in response_lower and " to " in response_lower:
        try:
            parts = response_lower.split("translate")[1].split(" to ")
            text = parts[0].strip()
            target_language = parts[1].strip() if len(parts) > 1 else "Spanish"
            result = command_processor.process_command('translate', text=text, target_language=target_language)
            logger.info(f"Translation command result: {result}")
            if result.get('success') and result.get('user_message'):
                command_executed_message = result['user_message']
        except Exception as e:
            logger.error(f"Error processing translation command: {e}")
            command_executed_message = f"Sorry, I couldn't translate that: {e}"
    
    # --- Use the helper function to play text ---
    text_to_speak = command_executed_message if command_executed_message else response
    _play_text_via_client(text_to_speak, current_user_id, current_conversation_id)


    if "CONVERSATION_END" in response:
        logger.info("Ending conversation as requested...")
        _log_and_commit(current_user_id, 'INFO', "Voice conversation ended by agent", current_conversation_id)
        conversation_active = False
        if conversation_instance:
            try:
                if hasattr(conversation_instance, 'audio_interface') and conversation_instance.audio_interface:
                    try:
                        conversation_instance.audio_interface.stop()
                        logger.info("Audio interface stopped.")
                    except Exception as audio_e:
                        logger.error(f"Error stopping audio interface: {audio_e}")
                conversation_instance.end_session()
                logger.info("Session ended gracefully.")
            except Exception as e:
                logger.error(f"Error ending session: {e}")

def print_interrupted_response(original, corrected):
    global conversation_instance
    logger.info(f"Agent interrupted, truncated response: {corrected}")
    _log_and_commit(current_user_id, 'INFO', f"Agent response interrupted: {corrected}", current_conversation_id)

def print_user_transcript(transcript):
    global current_user_id, current_conversation_id
    logger.info(f"User: {transcript}")
    
    _log_and_commit(current_user_id, 'USER', f"User said: {transcript}", current_conversation_id)
    
    end_phrases = ["end chat", "stop", "goodbye", "bye", "that's all", "thanks bye"]
    if any(phrase in transcript.lower() for phrase in end_phrases):
        logger.info("User wants to end conversation...")
        _log_and_commit(current_user_id, 'INFO', "User requested to end conversation", current_conversation_id)

def auto_shutdown_timer():
    global conversation_active, conversation_instance, current_user_id, current_conversation_id
    time.sleep(600) # 10 minutes
    if conversation_active:
        logger.info("Auto-shutdown: Ending conversation due to inactivity...")
        _log_and_commit(current_user_id, 'INFO', "Voice conversation ended due to inactivity (10 min timeout)", current_conversation_id)
        conversation_active = False
        if conversation_instance:
            try:
                if hasattr(conversation_instance, 'audio_interface') and conversation_instance.audio_interface:
                    try:
                        conversation_instance.audio_interface.stop()
                        logger.info("Audio interface stopped.")
                    except Exception as audio_e:
                        logger.error(f"Error stopping audio interface in auto-shutdown: {audio_e}")
                conversation_instance.end_session()
                logger.info("Session ended due to inactivity.")
            except Exception as e:
                logger.error(f"Error ending session in finally block: {e}")

def _start_voice_assistant_internal(user_id: uuid.UUID):
    """
    Internal function to start the ElevenLabs conversation session.
    Assumes an app context is already pushed.
    """
    global conversation_active, conversation_instance, current_user_id, current_conversation_id, ELEVENLABS_CLIENT, ELEVENLABS_AVAILABLE
    
    current_user_id = user_id
    conversation_active = True
    
    ELEVENLABS_CLIENT = None # Ensure client is reset for each attempt
    ELEVENLABS_AVAILABLE = False

    # Check if ElevenLabs core imports were successful at module level
    if not ELEVENLABS_IMPORTS_SUCCESS:
        error_msg = "ElevenLabs core modules failed to import at startup. Voice functionality is disabled."
        _log_and_commit(current_user_id, 'CRITICAL', error_msg, current_conversation_id)
        raise ImportError(error_msg)

    try:
        schedule = "Unable to fetch schedule at the moment."
        try:
            logger.info("Fetching today's schedule from Google Calendar within _start_voice_assistant_internal...")
            schedule = get_today_schedule()
            logger.info(f"Schedule retrieved: {schedule}")
        except Exception as e:
            logger.error(f"Error fetching schedule in _start_voice_assistant_internal: {e}")
            _log_and_commit(current_user_id, 'ERROR', f"Failed to fetch schedule: {str(e)}", current_conversation_id)

        user = User.query.get(user_id)
        user_name = user.get_full_name() if user and user.get_full_name() else user_name_placeholder

        session_id = str(uuid.uuid4())
        new_db_conversation = DBConversation(user_id=user_id, session_id=session_id)
        db.session.add(new_db_conversation)
        db.session.commit()
        current_conversation_id = new_db_conversation.id

        context_manager = ConversationContext(user_id=user_id, conversation_id=current_conversation_id)
        context = context_manager.get_context_for_prompt()

        dynamic_prompt = prompt_template.format(user_name=user_name, schedule=schedule)
        dynamic_prompt += f"\n\nAdditional Context:\n{context}"

        # Initialize ElevenLabs client and check availability
        try:
            if API_KEY and API_KEY != "your_elevenlabs_api_key_here":
                ELEVENLABS_CLIENT = ElevenLabs(api_key=API_KEY)
                # Verify the client has the 'generate' method
                if not hasattr(ELEVENLABS_CLIENT, 'generate'):
                    # This specific AttributeError is caught and re-raised for clarity
                    raise AttributeError("ElevenLabs client initialized but 'generate' method is missing. Check SDK version.")
                ELEVENLABS_AVAILABLE = True
                logger.info("ElevenLabs client initialized and 'generate' method verified.")
            else:
                logger.error("ElevenLabs API key is not set or is a placeholder in .env.")
                ELEVENLABS_AVAILABLE = False
        except AttributeError as e: # Catch the specific AttributeError during client setup
            logger.error(f"AttributeError during ElevenLabs client initialization: {e}")
            logger.error(traceback.format_exc())
            ELEVENLABS_AVAILABLE = False
            raise # Re-raise to ensure the outer try-except catches it and triggers retry
        except Exception as e:
            logger.error(f"General error initializing ElevenLabs client: {e}")
            logger.error(traceback.format_exc())
            ELEVENLABS_AVAILABLE = False
            raise # Re-raise to ensure the outer try-except catches it and triggers retry

        if not ELEVENLABS_AVAILABLE:
            error_msg = "ElevenLabs modules not available or API key invalid. Please check installation and .env."
            _log_and_commit(current_user_id, 'ERROR', error_msg, current_conversation_id)
            raise ImportError(error_msg) # Re-raise to trigger retry logic
        
        if not AGENT_ID or AGENT_ID == "your_elevenlabs_agent_id_here":
            error_msg = "Invalid ElevenLabs agent ID. Please check your .env file."
            _log_and_commit(current_user_id, 'ERROR', error_msg, current_conversation_id)
            raise ValueError(error_msg)
        
        logger.info("Starting voice assistant with Google Calendar integration...")
        _log_and_commit(current_user_id, 'INFO', "Voice assistant session starting with Google Calendar integration", current_conversation_id)
        
        conversation_config_override = {
            "agent": {
                "prompt": {
                    "prompt": dynamic_prompt,
                },
            },
        }

        dynamic_config = ConversationConfig(
            conversation_config_override=conversation_config_override,
            extra_body={},
            dynamic_variables={},
        )

        conversation_instance = Conversation(
            ELEVENLABS_CLIENT,
            AGENT_ID,
            config=dynamic_config,
            requires_auth=True,
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=print_agent_response,
            callback_agent_response_correction=print_interrupted_response,
            callback_user_transcript=print_user_transcript,
        )
        
        logger.info("Say 'goodbye', 'end chat', or 'stop' to end the conversation.")
        logger.info("To schedule events, say something like: 'Schedule a meeting with John tomorrow at 2pm'")
        
        _log_and_commit(current_user_id, 'INFO', "Voice assistant session initialized successfully", current_conversation_id)
        
        initial_greeting = f"Hello {user_name}! I can help you with anything, tell me what can I do."
        _play_text_via_client(initial_greeting, current_user_id, current_conversation_id)

        timer_thread = threading.Thread(target=auto_shutdown_timer, daemon=True)
        timer_thread.start()
        
        conversation_instance.start_session()
        
        while conversation_active:
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected. Ending conversation...")
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
