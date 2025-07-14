import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs.types import ConversationConfig
# Fix this import - remove 'backend.' prefix
from google_calendar_integration import (
    get_today_schedule, 
    get_upcoming_events,
    create_event_from_conversation,
    get_next_meeting,
    get_free_time_today
)
import threading
import time
load_dotenv()

AGENT_ID = os.getenv("AGENT_ID")
API_KEY = os.getenv("API_KEY")

user_name = "Chirag"

# Get real schedule from Google Calendar
try:
    print("Fetching today's schedule from Google Calendar...")
    schedule = get_today_schedule()
    print(f"Schedule retrieved: {schedule}")
except Exception as e:
    print(f"Error fetching schedule: {e}")
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

config = ConversationConfig(
    conversation_config_override=conversation_override,
    extra_body={},
    dynamic_variables={},
)

client = ElevenLabs(api_key=API_KEY)

# Global variable to control conversation state
conversation_active = True
conversation_instance = None

def print_agent_response(response):
    global conversation_active, conversation_instance
    print(f"Agent: {response}")
    
    # Check if agent wants to create a calendar event
    if "I'll create that event for you:" in response:
        # Extract the event description after the colon
        event_description = response.split("I'll create that event for you:")[1].strip()
        print(f"Creating calendar event: {event_description}")
        
        # Create the event
        try:
            result = create_event_from_conversation(event_description)
            print(f"Calendar result: {result}")
            # You could have the agent speak this result too
        except Exception as e:
            print(f"Error creating event: {e}")
    
    # Check if conversation should end
    if "CONVERSATION_END" in response:
        print("Ending conversation as requested...")
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                print("Session ended gracefully.")
            except Exception as e:
                print(f"Error ending session: {e}")

def print_interrupted_response(original, corrected):
    print(f"Agent interrupted, truncated response: {corrected}")

def print_user_transcript(transcript):
    print(f"User: {transcript}")
    
    # Check for explicit end commands from user
    end_phrases = ["end chat", "stop", "goodbye", "bye", "that's all", "thanks bye"]
    if any(phrase in transcript.lower() for phrase in end_phrases):
        print("User wants to end conversation...")

# Auto-shutdown timer (optional - conversation will end after 10 minutes of inactivity)
def auto_shutdown_timer():
    global conversation_active, conversation_instance
    time.sleep(600)  # 10 minutes
    if conversation_active:
        print("Auto-shutdown: Ending conversation due to inactivity...")
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                print("Session ended due to inactivity.")
            except Exception as e:
                print(f"Error ending session: {e}")

def start_voice_assistant():
    global conversation_active, conversation_instance
    
    try:
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
        
        print("Starting voice assistant with Google Calendar integration...")
        print("Say 'goodbye', 'end chat', or 'stop' to end the conversation.")
        print("To schedule events, say something like: 'Schedule a meeting with John tomorrow at 2pm'")
        
        # Start auto-shutdown timer
        timer_thread = threading.Thread(target=auto_shutdown_timer, daemon=True)
        timer_thread.start()
        
        conversation_instance.start_session()
        
        # Keep the conversation running until it's ended
        while conversation_active:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Ending conversation...")
        conversation_active = False
        if conversation_instance:
            try:
                conversation_instance.end_session()
                print("Session ended.")
            except Exception as e:
                print(f"Error ending session: {e}")
    except Exception as e:
        print(f"Error starting voice assistant: {e}")
        conversation_active = False
    finally:
        print("Voice assistant stopped.")

if __name__ == "__main__":
    start_voice_assistant()