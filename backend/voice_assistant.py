import os
from dotenv import load_dotenv
import logging
import threading
import time
from flask import current_app
import uuid # Import uuid for UUID objects

# Use relative imports because this file is inside the 'backend' package
from .memory import ConversationMemory
from .models import Conversation as DBConversation, Message, MessageType, db, User
from .command_processor import VoiceCommandProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import Google Calendar integration
from .google_calendar_integration import (
    get_today_schedule, 
    get_upcoming_events,
    create_event_from_conversation,
    get_next_meeting,
    get_free_time_today
)

# Database logging helper function for voice assistant
def log_voice_to_database(user_id, level, message, conversation_id=None, commit=True):
    """
    Log voice assistant events to the database
    
    Args:
        user_id (uuid.UUID or str): User ID (now UUID object or its string representation)
        level (str): Log level (INFO, ERROR, USER, AGENT, etc.)
        message (str): Log message
        conversation_id (int): The conversation ID to associate the log with.
        commit (bool): Whether to commit immediately (default True)
    """
    try:
        # Ensure user_id is a string if it's a UUID object for consistent storage
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id

        from .models import db, Log # Re-import to ensure latest model definition
        
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
        logger.error(f"Failed to log voice event to database: {e}")
        try:
            from models import db
            db.session.rollback()
        except Exception as rollback_e:
            logger.error(f"Error during rollback: {rollback_e}")


# Check for ElevenLabs dependencies
ELEVENLABS_AVAILABLE = False
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation
    from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
    from elevenlabs.types import ConversationConfig
    ELEVENLABS_AVAILABLE = True
except ImportError as e:
    logger.error(f"ElevenLabs import error: {e}")
    logger.error("Voice functionality will be limited. Please install with: pip install --upgrade elevenlabs")

# Get environment variables
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
API_KEY = os.getenv("ELEVENLABS_API_KEY")

# user_name will now be dynamically fetched from the User object
user_name_placeholder = "Chirag"

# Get real schedule from Google Calendar
try:
    logger.info("Fetching today's schedule from Google Calendar...")
    schedule = get_today_schedule()
    logger.info(f"Schedule retrieved: {schedule}")
except Exception as e:
    logger.error(f"Error fetching schedule: {e}")
    schedule = "Unable to fetch schedule at the moment"

# Enhanced prompt with more command capabilities (user_name will be dynamic)
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

first_message_template = "Hi {user_name}! I've got your schedule ready. I can help you view events, schedule meetings, or find free time. What would you like to do?"

# conversation_override will be created dynamically in start_voice_assistant

config = None
client = None

if ELEVENLABS_AVAILABLE:
    try:
        # Client initialization remains the same
        if API_KEY:
            client = ElevenLabs(api_key=API_KEY)
        else:
            logger.error("ElevenLabs API key not set in environment variables")
    except Exception as e:
        logger.error(f"Error configuring ElevenLabs client: {e}")
        ELEVENLABS_AVAILABLE = False

conversation_active = True
conversation_instance = None
current_user_id = None # This will be a UUID object
current_conversation_id = None

def print_agent_response(response):
    global conversation_active, conversation_instance, current_user_id, current_conversation_id
    logger.info(f"Agent: {response}")
    
    if current_user_id:
        log_voice_to_database(current_user_id, 'AGENT', f"Agent response: {response}", conversation_id=current_conversation_id)
    
    command_processor = VoiceCommandProcessor(user_id=current_user_id)
    command_processed = False

    response_lower = response.lower()
    
    # --- Command Processing Logic (remains largely the same) ---
    # Calendar Event Creation
    if "i'll create that event for you:" in response_lower:
        event_description = response.split("I'll create that event for you:")[1].strip()
        logger.info(f"Creating calendar event: {event_description}")
        
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', f"Voice assistant creating calendar event: {event_description}", conversation_id=current_conversation_id)
        
        try:
            result = create_event_from_conversation(event_description)
            logger.info(f"Calendar result: {result}")
            
            if current_user_id:
                log_voice_to_database(current_user_id, 'INFO', f"Calendar event created successfully: {event_description} - Result: {result}", conversation_id=current_conversation_id)
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            if current_user_id:
                log_voice_to_database(current_user_id, 'ERROR', f"Failed to create calendar event '{event_description}': {str(e)}", conversation_id=current_conversation_id)
        command_processed = True

    # Weather Command
    elif "weather in" in response_lower:
        try:
            location = response_lower.split("weather in")[1].strip().replace("?", "").replace(".", "")
            result = command_processor.process_command('weather', location=location)
            logger.info(f"Weather command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Weather response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing weather command: {e}")
        command_processed = True

    # News Command
    elif "news in" in response_lower:
        try:
            category = response_lower.split("news in")[1].strip().replace(".", "").replace("news", "").strip()
            result = command_processor.process_command('news', category=category)
            logger.info(f"News command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"News response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing news command: {e}")
        command_processed = True

    # Enhanced Reminder Command
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
                logger.info(f"Reminder response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing reminder command: {e}")
        command_processed = True

    # Enhanced Timer Command
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
                logger.info(f"Timer response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing timer command: {e}")
        command_processed = True

    # Note Command
    elif "note:" in response_lower:
        try:
            note_text = response.split(":", 1)[1].strip()
            result = command_processor.process_command('note', note_text=note_text)
            logger.info(f"Note command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Note response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing note command: {e}")
        command_processed = True

    # Calculator Command
    elif "calculate" in response_lower:
        try:
            expression = response_lower.split("calculate")[1].strip()
            expression = expression.replace("that", "").replace("this", "").strip()
            result = command_processor.process_command('calculate', expression=expression)
            logger.info(f"Calculator command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Calculator response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing calculator command: {e}")
        command_processed = True

    # Random Fact Command
    elif "random fact" in response_lower or "interesting fact" in response_lower:
        try:
            result = command_processor.process_command('fact')
            logger.info(f"Fact command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Fact response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing fact command: {e}")
        command_processed = True

    # Joke Command
    elif "tell joke" in response_lower or "tell me a joke" in response_lower:
        try:
            result = command_processor.process_command('joke')
            logger.info(f"Joke command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Joke response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing joke command: {e}")
        command_processed = True

    # Search Command
    elif "search for" in response_lower:
        try:
            query = response_lower.split("search for")[1].strip()
            result = command_processor.process_command('search', query=query)
            logger.info(f"Search command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Search response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing search command: {e}")
        command_processed = True

    # Translation Command
    elif "translate" in response_lower and " to " in response_lower:
        try:
            parts = response_lower.split("translate")[1].split(" to ")
            text = parts[0].strip()
            target_language = parts[1].strip() if len(parts) > 1 else "Spanish"
            result = command_processor.process_command('translate', text=text, target_language=target_language)
            logger.info(f"Translation command result: {result}")
            if result.get('success') and result.get('user_message'):
                logger.info(f"Translation response: {result['user_message']}")
        except Exception as e:
            logger.error(f"Error processing translation command: {e}")
        command_processed = True
    
    # Check if conversation should end
    if "CONVERSATION_END" in response:
        logger.info("Ending conversation as requested...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation ended by agent", conversation_id=current_conversation_id)
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                logger.info("Session ended gracefully.")
            except Exception as e:
                logger.error(f"Error ending session: {e}")

def print_interrupted_response(original, corrected):
    logger.info(f"Agent interrupted, truncated response: {corrected}")
    if current_user_id:
        log_voice_to_database(current_user_id, 'INFO', f"Agent response interrupted: {corrected}", conversation_id=current_conversation_id)

def print_user_transcript(transcript):
    global current_user_id, current_conversation_id
    logger.info(f"User: {transcript}")
    
    if current_user_id:
        log_voice_to_database(current_user_id, 'USER', f"User said: {transcript}", conversation_id=current_conversation_id)
    
    end_phrases = ["end chat", "stop", "goodbye", "bye", "that's all", "thanks bye"]
    if any(phrase in transcript.lower() for phrase in end_phrases):
        logger.info("User wants to end conversation...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "User requested to end conversation", conversation_id=current_conversation_id)

# Auto-shutdown timer
def auto_shutdown_timer():
    global conversation_active, conversation_instance, current_user_id, current_conversation_id
    time.sleep(600)
    if conversation_active:
        logger.info("Auto-shutdown: Ending conversation due to inactivity...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation ended due to inactivity (10 min timeout)", conversation_id=current_conversation_id)
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                logger.info("Session ended due to inactivity.")
            except Exception as e:
                logger.error(f"Error ending session: {e}")

def start_voice_assistant(user_id: uuid.UUID): # Expect user_id as UUID object
    global conversation_active, conversation_instance, current_user_id, current_conversation_id
    
    current_user_id = user_id # Store UUID object
    
    conversation_active = True
    conversation_instance = None
    
    try:
        with current_app.app_context():
            # Fetch user details to personalize prompt
            user = User.query.get(user_id)
            user_name = user.get_full_name() if user and user.get_full_name() else "Chirag" # Fallback

            # Create a new conversation record. user_id is a UUID object.
            session_id = str(uuid.uuid4()) # Generate a new session UUID
            new_db_conversation = DBConversation(user_id=user_id, session_id=session_id)
            db.session.add(new_db_conversation)
            db.session.commit()
            current_conversation_id = new_db_conversation.id

            memory = ConversationMemory(user_id)
            context = memory.get_context_for_prompt(current_conversation_id)

            # Dynamically format prompt and first message
            dynamic_prompt = prompt_template.format(user_name=user_name, schedule=schedule)
            dynamic_first_message = first_message_template.format(user_name=user_name)

            conversation_override = {
                "agent": {
                    "prompt": {
                        "prompt": dynamic_prompt,
                    },
                    "first_message": dynamic_first_message,
                },
            }
            # Recreate config with dynamic prompt
            dynamic_config = None
            if ELEVENLABS_AVAILABLE:
                dynamic_config = ConversationConfig(
                    conversation_config_override=conversation_override,
                    extra_body={},
                    dynamic_variables={},
                )

            if not ELEVENLABS_AVAILABLE:
                error_msg = "ElevenLabs modules not available. Please install with: pip install --upgrade elevenlabs"
                if current_user_id:
                    log_voice_to_database(current_user_id, 'ERROR', error_msg, conversation_id=current_conversation_id)
                raise ImportError(error_msg)
            
            if not API_KEY or API_KEY == "your_elevenlabs_api_key":
                error_msg = "Invalid ElevenLabs API key. Please check your .env file."
                if current_user_id:
                    log_voice_to_database(current_user_id, 'ERROR', error_msg, conversation_id=current_conversation_id)
                raise ValueError(error_msg)
                
            if not AGENT_ID or AGENT_ID == "your_elevenlabs_agent_id":
                error_msg = "Invalid ElevenLabs agent ID. Please check your .env file."
                if current_user_id:
                    log_voice_to_database(current_user_id, 'ERROR', error_msg, conversation_id=current_conversation_id)
                raise ValueError(error_msg)
            
            logger.info("Starting voice assistant with Google Calendar integration...")
            if current_user_id:
                log_voice_to_database(current_user_id, 'INFO', "Voice assistant session starting with Google Calendar integration", conversation_id=current_conversation_id)
            
            conversation_instance = Conversation(
                client,
                AGENT_ID,
                config=dynamic_config, # Use dynamic config
                requires_auth=True,
                audio_interface=DefaultAudioInterface(),
                callback_agent_response=print_agent_response,
                callback_agent_response_correction=print_interrupted_response,
                callback_user_transcript=print_user_transcript,
            )
            
            logger.info("Say 'goodbye', 'end chat', or 'stop' to end the conversation.")
            logger.info("To schedule events, say something like: 'Schedule a meeting with John tomorrow at 2pm'")
            
            if current_user_id:
                log_voice_to_database(current_user_id, 'INFO', "Voice assistant session initialized successfully", conversation_id=current_conversation_id)
            
            timer_thread = threading.Thread(target=auto_shutdown_timer, daemon=True)
            timer_thread.start()
            
            conversation_instance.start_session()
            
            while conversation_active:
                time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected. Ending conversation...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation interrupted by keyboard", conversation_id=current_conversation_id)
        conversation_active = False
    except ImportError as e:
        logger.error(f"Missing required modules: {e}")
        logger.error("Please install all required packages with: pip install --upgrade elevenlabs")
        if current_user_id:
            log_voice_to_database(current_user_id, 'ERROR', f"Voice assistant failed to start: {str(e)}", conversation_id=current_conversation_id)
        raise
    except Exception as e:
        logger.error(f"Error starting voice assistant: {e}")
        if current_user_id:
            log_voice_to_database(current_user_id, 'ERROR', f"Voice assistant error: {str(e)}", conversation_id=current_conversation_id)
        conversation_active = False
        raise
    finally:
        if conversation_instance:
            try:
                conversation_instance.end_session()
            except:
                pass
        logger.info("Voice assistant stopped.")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice assistant session ended", conversation_id=current_conversation_id)

def start_voice_assistant_with_retry(user_id=None, max_retries=3):
    # user_id will be a UUID object here
    for attempt in range(max_retries):
        try:
            return start_voice_assistant(user_id)
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                log_voice_to_database(user_id, 'INFO', f"Retrying voice assistant (attempt {attempt + 2})")
                time.sleep(2)
            else:
                log_voice_to_database(user_id, 'ERROR', f"Voice assistant failed after {max_retries} attempts")
                raise
