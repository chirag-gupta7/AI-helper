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

# Define the scope for read-only access to calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    """
    Authenticate and return Google Calendar service object.
    This handles the OAuth flow and token management.
    """
    creds = None
    
    # Check if we have stored credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials available, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                # Delete the token file and re-authenticate
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                creds = None
        
        if not creds:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def get_today_schedule():
    """
    Get today's schedule from Google Calendar.
    Returns a formatted string with today's events.
    """
    try:
        service = authenticate_google_calendar()
        
        # Get today's date range (in UTC)
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Call the Calendar API
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
            # Get event title
            summary = event.get('summary', 'Untitled Event')
            
            # Get start time
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:  # dateTime format (timed event)
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = start_time.strftime('%H:%M')
            else:  # date format (all-day event)
                time_str = 'All day'
            
            # Get location if available
            location = event.get('location', '')
            location_str = f" at {location}" if location else ""
            
            schedule_items.append(f"{summary} at {time_str}{location_str}")
        
        return "; ".join(schedule_items)
    
    except HttpError as error:
        print(f"An error occurred: {error}")
        return "Unable to fetch calendar events"
    except Exception as error:
        print(f"An unexpected error occurred: {error}")
        return "Unable to fetch calendar events"

def get_upcoming_events(days_ahead=7):
    """
    Get upcoming events for the next specified number of days.
    """
    try:
        service = authenticate_google_calendar()
        
        # Get time range
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
        print(f"An error occurred: {error}")
        return "Unable to fetch upcoming events"

def get_next_meeting():
    """Get the next upcoming meeting."""
    try:
        service = authenticate_google_calendar()
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
        return "Unable to fetch next meeting"

def get_free_time_today():
    """Find free time slots in today's schedule."""
    try:
        service = authenticate_google_calendar()
        
        # Get today's events
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
        
        # Simple free time calculation (you can make this more sophisticated)
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
        
        # Sort by start time
        busy_times.sort(key=lambda x: x[0])
        
        # Find gaps (simplified logic)
        free_slots = []
        current_time = now
        
        for start, end in busy_times:
            if current_time < start:
                duration = start - current_time
                if duration.total_seconds() > 3600:  # More than 1 hour
                    free_slots.append(f"{current_time.strftime('%H:%M')} - {start.strftime('%H:%M')}")
            current_time = max(current_time, end)
        
        if free_slots:
            return f"Free time slots: {'; '.join(free_slots)}"
        else:
            return "No significant free time slots found today"
    
    except Exception as error:
        return "Unable to calculate free time"

def parse_natural_language_datetime(text):
    """
    Parse natural language datetime expressions.
    """
    text = text.lower().strip()
    now = datetime.now()
    
    # Handle relative dates
    if 'tomorrow' in text:
        base_date = now + timedelta(days=1)
    elif 'today' in text:
        base_date = now
    elif 'next week' in text:
        base_date = now + timedelta(weeks=1)
    elif 'next month' in text:
        base_date = now + relativedelta(months=1)
    else:
        # Try to parse with dateutil
        try:
            base_date = parser.parse(text, fuzzy=True)
        except:
            base_date = now
    
    # Extract time if present
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)',
        r'(\d{1,2})\s*(am|pm)',
        r'(\d{1,2}):(\d{2})',
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) == 3:  # Hour:minute am/pm
                hour = int(match.group(1))
                minute = int(match.group(2))
                ampm = match.group(3)
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
            elif len(match.groups()) == 2 and match.group(2) in ['am', 'pm']:  # Hour am/pm
                hour = int(match.group(1))
                minute = 0
                ampm = match.group(2)
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
            else:  # 24-hour format
                hour = int(match.group(1))
                minute = int(match.group(2))
            
            base_date = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            break
    
    return base_date

def create_event_from_conversation(conversation_text):
    """
    Create a calendar event from natural language conversation text.
    Enhanced version with better parsing.
    """
    try:
        service = authenticate_google_calendar()
        
        # Clean up the text
        text = conversation_text.strip()
        
        # Try Google's quick add first (it's very good at natural language)
        try:
            event = service.events().quickAdd(
                calendarId='primary',
                text=text
            ).execute()
            
            # Format success response
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
                # If quick add fails, try manual parsing
                return create_event_manual_parse(text)
            else:
                raise error
                
    except Exception as error:
        return f"❌ Error creating event: {error}"

def create_event_manual_parse(text):
    """
    Manual parsing when Google's quick add fails.
    """
    try:
        service = authenticate_google_calendar()
        
        # Extract basic info
        # Simple title extraction (everything before time/date info)
        title_match = re.match(r'^([^0-9]+?)(?:\s+(?:on|at|tomorrow|today|next|this))', text, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = text.split()[0:3]  # First few words as title
            title = ' '.join(title)
        
        # Parse datetime
        event_datetime = parse_natural_language_datetime(text)
        
        # Default duration: 1 hour
        end_datetime = event_datetime + timedelta(hours=1)
        
        # Create the event
        event = {
            'summary': title,
            'start': {
                'dateTime': event_datetime.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        event_result = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        time_str = event_datetime.strftime('%B %d, %Y at %I:%M %p')
        return f"✅ Event created: '{title}' on {time_str}"
        
    except Exception as error:
        return f"❌ Error with manual parsing: {error}"

# Keep all the existing functions (create_event, update_event, etc.) as they were...
def create_event(summary, start_time, end_time, description=None, location=None):
    """
    Create a new calendar event.
    """
    try:
        service = authenticate_google_calendar()
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        if description:
            event['description'] = description
        if location:
            event['location'] = location
        
        event_result = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        return f"Event created successfully: {event_result.get('htmlLink')}"
    
    except Exception as error:
        return f"Error creating event: {error}"

def test_calendar_connection():
    """
    Test the calendar connection and print some basic info.
    """
    try:
        service = authenticate_google_calendar()
        
        calendar = service.calendars().get(calendarId='primary').execute()
        print(f"Successfully connected to calendar: {calendar.get('summary', 'Primary Calendar')}")
        
        today_schedule = get_today_schedule()
        print(f"Today's schedule: {today_schedule}")
        
        return True
    except Exception as error:
        print(f"Connection test failed: {error}")
        return False

# Test the calendar integration
if __name__ == "__main__":
    print("Testing calendar integration...")
    test_calendar_connection()
    
    # Test event creation
    print("\nTesting event creation...")
    test_events = [
        "Meeting with John tomorrow at 2pm",
        "Gym session Friday 6pm",
        "Dentist appointment next Monday at 10am"
    ]
    
    for event_text in test_events:
        result = create_event_from_conversation(event_text)
        print(f"'{event_text}' -> {result}")