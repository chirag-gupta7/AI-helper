import os
import pickle
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from dateutil import parser
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)

# Define the scope for read-only access to calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- Corrected Code: Build absolute paths to the files ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
# ---

# Global variable to hold the authenticated service object
# This will be managed by the Flask app context for efficiency
_cached_calendar_service = None

def authenticate_google_calendar():
    """
    Authenticate and return Google Calendar service object.
    This handles the OAuth flow and token management.
    This function should ideally be called once and its result cached.
    """
    creds = None
    
    # Check if we have stored credentials using the absolute path
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            logger.error(f"Error loading token.pickle: {e}")
            creds = None # Force re-authentication

    # If there are no valid credentials available, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Google Calendar credentials refreshed.")
            except Exception as e:
                logger.error(f"Error refreshing Google Calendar credentials: {e}")
                # Delete the token file and re-authenticate
                if os.path.exists(TOKEN_PATH):
                    os.remove(TOKEN_PATH)
                    logger.warning("Deleted expired/invalid token.pickle to force re-authentication.")
                creds = None
        
        if not creds:
            # Check for credentials.json using the absolute path
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "credentials.json not found. Please place it in the 'backend' directory."
                )
            
            logger.info("Initiating full Google Calendar OAuth flow...")
            # Load credentials from the absolute path
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Google Calendar OAuth flow completed successfully.")
        
        # Save credentials for future use using the absolute path
        try:
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)
            logger.info("Google Calendar token saved to token.pickle.")
        except Exception as e:
            logger.error(f"Error saving token.pickle: {e}")

    return build('calendar', 'v3', credentials=creds)

def get_calendar_service():
    """
    Provides the authenticated Google Calendar service object.
    Caches the service object for efficiency.
    """
    global _cached_calendar_service
    if _cached_calendar_service is None:
        logger.info("Google Calendar service not cached, authenticating now...")
        _cached_calendar_service = authenticate_google_calendar()
        logger.info("Google Calendar service cached.")
    return _cached_calendar_service

def get_today_schedule():
    """
    Get today's schedule from Google Calendar.
    Returns a formatted string with today's events.
    """
    try:
        # Use the cached service
        service = get_calendar_service()
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat() + 'Z',
            timeMax=today_end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "No events scheduled for today"
        
        schedule_items = []
        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = start_time.strftime('%H:%M')
            else:
                time_str = 'All day'
            
            location = event.get('location', '')
            location_str = f" at {location}" if location else ""
            
            schedule_items.append(f"{summary} at {time_str}{location_str}")
        
        return "; ".join(schedule_items)
    
    except HttpError as error:
        logger.error(f"An HTTP error occurred with Google Calendar API: {error}")
        return "Unable to fetch calendar events"
    except Exception as error:
        logger.error(f"An unexpected error occurred while fetching calendar events: {error}")
        return "Unable to fetch calendar events"

def get_upcoming_events(days_ahead=7):
    """
    Get upcoming events for the next specified number of days.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"No events scheduled for the next {days_ahead} days"
        
        schedule_items = []
        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                date_str = start_time.strftime('%Y-%m-%d')
                time_str = start_time.strftime('%H:%M')
                schedule_items.append(f"{summary} on {date_str} at {time_str}")
            else:
                schedule_items.append(f"{summary} on {start} (All day)")
        
        return "; ".join(schedule_items)
    
    except Exception as error:
        logger.error(f"An error occurred while fetching upcoming events: {error}")
        return "Unable to fetch upcoming events"

def get_next_meeting():
    """Get the next upcoming meeting."""
    try:
        service = get_calendar_service() # Use the cached service
        now = datetime.utcnow()
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            maxResults=1,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "No upcoming meetings"
        
        event = events[0]
        summary = event.get('summary', 'Untitled Event')
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        if 'T' in start:
            start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
            time_str = start_time.strftime('%H:%M on %B %d')
        else:
            time_str = f"All day on {start}"
        
        return f"Next meeting: {summary} at {time_str}"
    
    except Exception as error:
        logger.error(f"An error occurred while fetching next meeting: {error}")
        return "Unable to fetch next meeting"

def get_free_time_today():
    """Find free time slots in today's schedule."""
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat() + 'Z',
            timeMax=today_end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "You have the whole day free!"
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')
            
            if start and end:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
                busy_times.append((start_time, end_time))
        
        if not busy_times:
            return "No timed events today, mostly free!"
        
        busy_times.sort(key=lambda x: x[0])
        
        free_slots = []
        current_time = now
        
        for start, end in busy_times:
            if current_time < start:
                duration = start - current_time
                if duration.total_seconds() > 3600: # Only consider slots longer than 1 hour
                    free_slots.append(f"{current_time.strftime('%H:%M')} - {start.strftime('%H:%M')}")
            current_time = max(current_time, end)
        
        # Check for free time after the last event until end of day (e.g., 5 PM work day end)
        end_of_work_day = today_start.replace(hour=17, minute=0, second=0, microsecond=0)
        if current_time < end_of_work_day:
            duration = end_of_work_day - current_time
            if duration.total_seconds() > 3600:
                free_slots.append(f"{current_time.strftime('%H:%M')} - {end_of_work_day.strftime('%H:%M')}")


        if free_slots:
            return f"Free time slots: {'; '.join(free_slots)}"
        else:
            return "No significant free time slots found today"
    
    except Exception as error:
        logger.error(f"An error occurred while getting free time: {error}")
        return "Unable to calculate free time"

def parse_natural_language_datetime(text):
    """
    Parse natural language datetime expressions.
    """
    text = text.lower().strip()
    now = datetime.now()
    
    if 'tomorrow' in text:
        base_date = now + timedelta(days=1)
    elif 'today' in text:
        base_date = now
    elif 'next week' in text:
        base_date = now + timedelta(weeks=1)
    elif 'next month' in text:
        base_date = now + relativedelta(months=1)
    else:
        try:
            base_date = parser.parse(text, fuzzy=True)
        except:
            base_date = now
    
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)',
        r'(\d{1,2})\s*(am|pm)',
        r'(\d{1,2}):(\d{2})',
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) == 3:
                hour = int(match.group(1))
                minute = int(match.group(2))
                ampm = match.group(3)
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
            elif len(match.groups()) == 2 and match.group(2) in ['am', 'pm']:
                hour = int(match.group(1))
                minute = 0
                ampm = match.group(2)
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
            else:
                hour = int(match.group(1))
                minute = int(match.group(2))
            
            base_date = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            break
    
    return base_date

# --- NEW FUNCTION: create_event_manual_parse ---
def create_event_manual_parse(conversation_text):
    """
    Manually parses conversation text to create a calendar event.
    This is a fallback if quickAdd fails.
    """
    logger.info(f"Attempting manual parse for event: {conversation_text}")
    summary = "Untitled Event"
    start_time = datetime.utcnow() + timedelta(hours=1) # Default to 1 hour from now
    end_time = start_time + timedelta(hours=1) # Default duration 1 hour
    
    # Simple regex to find common patterns for event summary
    # This regex is improved to be more robust
    summary_match = re.search(r'(?:schedule|create|add)\s+(?:a\s+)?(.+?)(?:\s+(?:on|at|for|from)\s+.*|$)', conversation_text, re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip()
        # Clean up summary if it contains time/date phrases that were part of the summary extraction
        # This is a heuristic and might need further refinement based on user input patterns
        summary = re.sub(r'(?:tomorrow|today|next week|next month|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|on \w+ \d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?::\d{2})?\s*(?:am|pm)?).*', '', summary, flags=re.IGNORECASE).strip()
        if not summary: # Fallback if regex removed everything
            summary = "New Event"
    else:
        # If no clear summary found, use the whole text or a default
        summary = conversation_text.split(' for ')[0].strip() if ' for ' in conversation_text else "New Event"
        if len(summary) > 100: # Prevent very long summaries
            summary = summary[:100] + "..."


    # Try to parse date/time from the text
    try:
        parsed_datetime = parse_natural_language_datetime(conversation_text)
        start_time = parsed_datetime
        end_time = start_time + timedelta(hours=1) # Default to 1 hour duration
        logger.info(f"Manually parsed start time: {start_time}")
    except Exception as dt_error:
        logger.warning(f"Could not parse date/time from '{conversation_text}': {dt_error}. Using default times.")

    # Call the existing create_event function
    return create_event(summary, start_time, end_time, description=conversation_text)

# --- END NEW FUNCTION ---

# --- Moved create_event_from_conversation here (before __main__ block) ---
def create_event_from_conversation(conversation_text):
    """
    Create a calendar event from natural language conversation text.
    """
    try:
        service = get_calendar_service() # Use the cached service
        text = conversation_text.strip()
        
        try:
            event = service.events().quickAdd(
                calendarId='primary',
                text=text
            ).execute()
            
            summary = event.get('summary', 'Event')
            start_info = event.get('start', {})
            
            if start_info.get('dateTime'):
                start_time = datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00'))
                time_str = start_time.strftime('%B %d, %Y at %I:%M %p')
                return f"✅ Event created: '{summary}' on {time_str}"
            elif start_info.get('date'):
                date_str = start_info['date']
                return f"✅ All-day event created: '{summary}' on {date_str}"
            else:
                return f"✅ Event created: '{summary}'"
                
        except HttpError as error:
            if error.resp.status == 400:
                logger.warning(f"Google QuickAdd failed, attempting manual parse: {error}")
                return create_event_manual_parse(text)
            else:
                raise error
                
    except Exception as error:
        logger.error(f"Error creating event from conversation: {error}")
        return f"❌ Error creating event: {error}"
# --- End of moved create_event_from_conversation ---

def create_event(summary, start_time, end_time, description=None, location=None):
    """
    Create a new calendar event.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        event = {
            'summary': summary,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }
        
        if description:
            event['description'] = description
        if location:
            event['location'] = location
        
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created successfully: {event_result.get('htmlLink')}"
    
    except Exception as error:
        logger.error(f"Error creating event: {error}")
        return f"Error creating event: {error}"

def reschedule_event(event_id, new_start_time_iso):
    """
    Reschedule an existing event to a new time.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        new_start_time = parser.isoparse(new_start_time_iso)
        
        original_start = parser.isoparse(event['start']['dateTime'])
        original_end = parser.isoparse(event['end']['dateTime'])
        duration = original_end - original_start
        new_end_time = new_start_time + duration
        
        event['start']['dateTime'] = new_start_time.isoformat()
        event['end']['dateTime'] = new_end_time.isoformat()

        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        
        time_str = new_start_time.strftime('%B %d, %Y at %I:%M %p')
        return f"✅ Event '{updated_event['summary']}' rescheduled to {time_str}."
    except Exception as error:
        logger.error(f"Error rescheduling event: {error}")
        return f"❌ Error rescheduling event: {error}"

def cancel_event(event_id):
    """
    Cancel a calendar event.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        summary = event.get('summary', 'Unknown Event')

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        return f"✅ Event '{summary}' has been canceled."
    except HttpError as error:
        if error.resp.status == 410:
            return "✅ Event has already been canceled."
        logger.error(f"HTTP error canceling event: {error}")
        return f"❌ Error canceling event: {error}"
    except Exception as error:
        logger.error(f"An unexpected error occurred canceling event: {error}")
        return f"❌ Error canceling event: {error}"

def find_meeting_slots(duration_minutes, participants_str, days_ahead=7):
    """
    Find available meeting slots considering all participants' calendars.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        time_min_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        time_max_dt = now + timedelta(days=days_ahead)
        
        participants = [p.strip() for p in participants_str.split(',') if p.strip()]
        if 'primary' not in participants:
            participants.append('primary')

        freebusy_query = {
            "timeMin": time_min_dt.isoformat() + 'Z',
            "timeMax": time_max_dt.isoformat() + 'Z',
            "items": [{"id": p} for p in participants],
        }
        
        freebusy_result = service.freebusy().query(body=freebusy_query).execute()
        
        busy_slots = []
        for cal_id, data in freebusy_result['calendars'].items():
            busy_slots.extend(data['busy'])
            
        if not busy_slots:
            return ["Everyone is free for the next 7 days during work hours."]

        busy_times = sorted([(parser.isoparse(slot['start']), parser.isoparse(slot['end'])) for slot in busy_slots])
        
        merged_busy = []
        if busy_times:
            current_start, current_end = busy_times[0]
            for next_start, next_end in busy_times[1:]:
                if next_start < current_end:
                    current_end = max(current_end, next_end)
                else:
                    merged_busy.append((current_start, current_end))
                    current_start, current_end = next_start, next_end
            merged_busy.append((current_start, current_end))

        free_slots = []
        search_time = time_min_dt
        duration = timedelta(minutes=duration_minutes)

        while search_time < time_max_dt and len(free_slots) < 5:
            if search_time.hour >= 17: # End searching at 5 PM
                search_time = (search_time + timedelta(days=1)).replace(hour=9, minute=0) # Start next day at 9 AM
                continue
            if search_time.hour < 9: # Start searching from 9 AM
                search_time = search_time.replace(hour=9, minute=0)
                continue

            potential_end_time = search_time + duration
            is_free = True
            for busy_start, busy_end in merged_busy:
                # Check for overlap
                if max(search_time, busy_start) < min(potential_end_time, busy_end):
                    is_free = False
                    search_time = busy_end # Move search time past the busy slot
                    break
            
            if is_free:
                free_slots.append(search_time.strftime('%A, %b %d at %I:%M %p'))
                search_time += timedelta(minutes=30) # Move to next potential slot
            
        return free_slots if free_slots else ["No common slots found."]

    except Exception as error:
        logger.error(f"Error finding meeting slots: {error}")
        return [f"❌ Error finding slots: {error}"]

def set_event_reminder(event_id, minutes_before):
    """
    Set a custom reminder for an event.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        event['reminders'] = {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': minutes_before},
                {'method': 'email', 'minutes': minutes_before},
            ],
        }

        updated_event = service.events().update(
            calendarId='primary', eventId=event_id, body=event
        ).execute()

        return f"✅ Reminder set for '{updated_event['summary']}' ({minutes_before} minutes before)."
    except Exception as error:
        logger.error(f"Error setting reminder: {error}")
        return f"❌ Error setting reminder: {error}"

def test_calendar_connection():
    """
    Test the calendar connection and print some basic info.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        calendar = service.calendars().get(calendarId='primary').execute()
        logger.info(f"Successfully connected to calendar: {calendar.get('summary', 'Primary Calendar')}")
        
        # No need to get today's schedule here, as it's a separate API call.
        # This function just confirms the *connection* is possible.
        
        return True
    except Exception as error:
        logger.error(f"Calendar connection test failed: {error}")
        return False

if __name__ == "__main__":
    print("Testing calendar integration...")
    test_calendar_connection()
    
    print("\nTesting event creation...")
    test_events = [
        "Meeting with John tomorrow at 2pm",
        "Gym session Friday 6pm",
        "Dentist appointment next Monday at 10am"
    ]
    
    for event_text in test_events:
        result = create_event_from_conversation(event_text)
        print(f"'{event_text}' -> {result}")

