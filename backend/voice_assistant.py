import os
from dotenv import load_dotenv
import logging
import threading
import time
from flask import current_app

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import Google Calendar integration
from google_calendar_integration import (
    get_today_schedule, 
    get_upcoming_events,
    create_event_from_conversation,
    get_next_meeting,
    get_free_time_today
)

# Database logging helper function for voice assistant
def log_voice_to_database(user_id, level, message, commit=True):
    """
    Log voice assistant events to the database
    
    Args:
        user_id (str): User ID from session
        level (str): Log level (INFO, ERROR, USER, AGENT, etc.)
        message (str): Log message
        commit (bool): Whether to commit immediately (default True)
    """
    try:
        # Import here to avoid circular imports
        from models import db, Log
        
        new_log = Log(
            user_id=user_id,
            level=level,
            message=message
        )
        db.session.add(new_log)
        if commit:
            db.session.commit()
    except Exception as e:
        # Don't let database logging errors break the voice functionality
        logger.error(f"Failed to log voice event to database: {e}")
        # Try to rollback if there was an issue
        try:
            from models import db
            db.session.rollback()
        except:
            pass

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
AGENT_ID = os.getenv("AGENT_ID")
API_KEY = os.getenv("API_KEY")

user_name = "Chirag"

# Get real schedule from Google Calendar
try:
    logger.info("Fetching today's schedule from Google Calendar...")
    schedule = get_today_schedule()
    logger.info(f"Schedule retrieved: {schedule}")
except Exception as e:
    logger.error(f"Error fetching schedule: {e}")
    schedule = "Unable to fetch schedule at the moment"

# Enhanced prompt with calendar management capabilities
prompt = f"""You are Chirag's personal assistant with Google Calendar integration. Today's schedule: {schedule}

CAPABILITIES:
- View today's schedule and upcoming events
- Create calendar events from natural language
- Find free time slots
- Check next meeting

CALENDAR EVENT CREATION:
When users want to schedule something, extract the details and respond with:
"I'll create that event for you: [event description]"

For example:
- "Schedule a meeting with John tomorrow at 2pm" 
- "Add gym session Friday 6pm"
- "Book dentist appointment next Monday 10am"

ENDING CONVERSATION:
When the user says goodbye, wants to end the chat, or says phrases like:
- "That's all", "Thanks, bye", "End chat", "Stop", "Goodbye", "See you later"
Respond with: "Goodbye! Have a great day, Chirag. CONVERSATION_END"

Keep responses brief and helpful."""

first_message = f"Hi Chirag! I've got your schedule ready. I can help you view events, schedule meetings, or find free time. What would you like to do?"

conversation_override = {
    "agent": {
        "prompt": {
            "prompt": prompt,
        },
        "first_message": first_message,
    },
}

config = None
client = None

# Only configure ElevenLabs if available
if ELEVENLABS_AVAILABLE:
    try:
        config = ConversationConfig(
            conversation_config_override=conversation_override,
            extra_body={},
            dynamic_variables={},
        )

        # Initialize ElevenLabs client
        if API_KEY:
            client = ElevenLabs(api_key=API_KEY)
        else:
            logger.error("ElevenLabs API key not set in environment variables")
    except Exception as e:
        logger.error(f"Error configuring ElevenLabs: {e}")
        ELEVENLABS_AVAILABLE = False

# Global variable to control conversation state
conversation_active = True
conversation_instance = None
current_user_id = None

def print_agent_response(response):
    global conversation_active, conversation_instance, current_user_id
    logger.info(f"Agent: {response}")
    
    # Log agent response to database
    if current_user_id:
        log_voice_to_database(current_user_id, 'AGENT', f"Agent response: {response}")
    
    # Check if agent wants to create a calendar event
    if "I'll create that event for you:" in response:
        # Extract the event description after the colon
        event_description = response.split("I'll create that event for you:")[1].strip()
        logger.info(f"Creating calendar event: {event_description}")
        
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', f"Voice assistant creating calendar event: {event_description}")
        
        # Create the event
        try:
            result = create_event_from_conversation(event_description)
            logger.info(f"Calendar result: {result}")
            
            if current_user_id:
                log_voice_to_database(current_user_id, 'INFO', f"Calendar event created successfully: {event_description} - Result: {result}")
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            if current_user_id:
                log_voice_to_database(current_user_id, 'ERROR', f"Failed to create calendar event '{event_description}': {str(e)}")
    
    # Check if conversation should end
    if "CONVERSATION_END" in response:
        logger.info("Ending conversation as requested...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation ended by agent")
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
        log_voice_to_database(current_user_id, 'INFO', f"Agent response interrupted: {corrected}")

def print_user_transcript(transcript):
    global current_user_id
    logger.info(f"User: {transcript}")
    
    # Log user input to database
    if current_user_id:
        log_voice_to_database(current_user_id, 'USER', f"User said: {transcript}")
    
    # Check for explicit end commands from user
    end_phrases = ["end chat", "stop", "goodbye", "bye", "that's all", "thanks bye"]
    if any(phrase in transcript.lower() for phrase in end_phrases):
        logger.info("User wants to end conversation...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "User requested to end conversation")

# Auto-shutdown timer
def auto_shutdown_timer():
    global conversation_active, conversation_instance, current_user_id
    time.sleep(600)  # 10 minutes
    if conversation_active:
        logger.info("Auto-shutdown: Ending conversation due to inactivity...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation ended due to inactivity (10 min timeout)")
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                logger.info("Session ended due to inactivity.")
            except Exception as e:
                logger.error(f"Error ending session: {e}")

def start_voice_assistant(user_id=None):
    global conversation_active, conversation_instance, current_user_id
    
    # Set the current user ID for logging
    current_user_id = user_id
    
    # Reset conversation state
    conversation_active = True
    conversation_instance = None
    
    try:
        # Check if ElevenLabs is available
        if not ELEVENLABS_AVAILABLE:
            error_msg = "ElevenLabs modules not available. Please install with: pip install --upgrade elevenlabs"
            if current_user_id:
                log_voice_to_database(current_user_id, 'ERROR', error_msg)
            raise ImportError(error_msg)
        
        # Check API key and Agent ID
        if not API_KEY or API_KEY == "your_elevenlabs_api_key":
            error_msg = "Invalid ElevenLabs API key. Please check your .env file."
            if current_user_id:
                log_voice_to_database(current_user_id, 'ERROR', error_msg)
            raise ValueError(error_msg)
            
        if not AGENT_ID or AGENT_ID == "your_elevenlabs_agent_id":
            error_msg = "Invalid ElevenLabs agent ID. Please check your .env file."
            if current_user_id:
                log_voice_to_database(current_user_id, 'ERROR', error_msg)
            raise ValueError(error_msg)
        
        logger.info("Starting voice assistant with Google Calendar integration...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice assistant session starting with Google Calendar integration")
        
        # Create the conversation instance
        conversation_instance = Conversation(
            client,
            AGENT_ID,
            config=config,
            requires_auth=True,
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=print_agent_response,
            callback_agent_response_correction=print_interrupted_response,
            callback_user_transcript=print_user_transcript,
        )
        
        logger.info("Say 'goodbye', 'end chat', or 'stop' to end the conversation.")
        logger.info("To schedule events, say something like: 'Schedule a meeting with John tomorrow at 2pm'")
        
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice assistant session initialized successfully")
        
        # Start auto-shutdown timer
        timer_thread = threading.Thread(target=auto_shutdown_timer, daemon=True)
        timer_thread.start()
        
        # Start conversation
        conversation_instance.start_session()
        
        # Keep the conversation running until it's ended
        while conversation_active:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected. Ending conversation...")
        if current_user_id:
            log_voice_to_database(current_user_id, 'INFO', "Voice conversation interrupted by keyboard")
        conversation_active = False
    except ImportError as e:
        logger.error(f"Missing required modules: {e}")
        logger.error("Please install all required packages with: pip install --upgrade elevenlabs")
        if current_user_id:
            log_voice_to_database(current_user_id, 'ERROR', f"Voice assistant failed to start: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error starting voice assistant: {e}")
        if current_user_id:
            log_voice_to_database(current_user_id, 'ERROR', f"Voice assistant error: {str(e)}")
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
            log_voice_to_database(current_user_id, 'INFO', "Voice assistant session ended")