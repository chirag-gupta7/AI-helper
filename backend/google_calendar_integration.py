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

# --- Corrected Code: Build absolute paths to the files ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
# ---

def authenticate_google_calendar():
    """
    Authenticate and return Google Calendar service object.
    This handles the OAuth flow and token management.
    """
    creds = None
    
    # Check if we have stored credentials using the absolute path
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials available, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                # Delete the token file and re-authenticate
                if os.path.exists(TOKEN_PATH):
                    os.remove(TOKEN_PATH)
                creds = None
        
        if not creds:
            # Check for credentials.json using the absolute path
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "credentials.json not found. Please place it in the 'backend' directory."
                )
            
            # Load credentials from the absolute path
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use using the absolute path
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def get_today_schedule():
    """
    Get today's schedule from Google Calendar.
    Returns a formatted string with today's events.
    """
    try:
        service = authenticate_google_calendar()
        
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
                if duration.total_seconds() > 3600:
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

def create_event_from_conversation(conversation_text):
    """
    Create a calendar event from natural language conversation text.
    """
    try:
        service = authenticate_google_calendar()
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
        
        title_match = re.match(r'^([^0-9]+?)(?:\s+(?:on|at|tomorrow|today|next|this))', text, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = ' '.join(text.split()[0:3])
        
        event_datetime = parse_natural_language_datetime(text)
        end_datetime = event_datetime + timedelta(hours=1)
        
        event = {
            'summary': title,
            'start': {'dateTime': event_datetime.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_datetime.isoformat(), 'timeZone': 'UTC'},
        }
        
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        time_str = event_datetime.strftime('%B %d, %Y at %I:%M %p')
        return f"✅ Event created: '{title}' on {time_str}"
        
    except Exception as error:
        return f"❌ Error with manual parsing: {error}"

def create_event(summary, start_time, end_time, description=None, location=None):
    """
    Create a new calendar event.
    """
    try:
        service = authenticate_google_calendar()
        
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
        return f"Error creating event: {error}"

def reschedule_event(event_id, new_start_time_iso):
    """
    Reschedule an existing event to a new time.
    """
    try:
        service = authenticate_google_calendar()
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
        return f"❌ Error rescheduling event: {error}"

def cancel_event(event_id):
    """
    Cancel a calendar event.
    """
    try:
        service = authenticate_google_calendar()
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        summary = event.get('summary', 'Unknown Event')

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        return f"✅ Event '{summary}' has been canceled."
    except HttpError as error:
        if error.resp.status == 410:
            return "✅ Event has already been canceled."
        return f"❌ Error canceling event: {error}"
    except Exception as error:
        return f"❌ Error canceling event: {error}"

def find_meeting_slots(duration_minutes, participants_str, days_ahead=7):
    """
    Find available meeting slots considering all participants' calendars.
    """
    try:
        service = authenticate_google_calendar()
        
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
            if search_time.hour >= 17:
                search_time = (search_time + timedelta(days=1)).replace(hour=9, minute=0)
                continue
            if search_time.hour < 9:
                search_time = search_time.replace(hour=9, minute=0)
                continue

            potential_end_time = search_time + duration
            is_free = True
            for busy_start, busy_end in merged_busy:
                if max(search_time, busy_start) < min(potential_end_time, busy_end):
                    is_free = False
                    search_time = busy_end
                    break
            
            if is_free:
                free_slots.append(search_time.strftime('%A, %b %d at %I:%M %p'))
                search_time += timedelta(minutes=30)
            
        return free_slots if free_slots else ["No common slots found."]

    except Exception as error:
        return [f"❌ Error finding slots: {error}"]

def set_event_reminder(event_id, minutes_before):
    """
    Set a custom reminder for an event.
    """
    try:
        service = authenticate_google_calendar()
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
        return f"❌ Error setting reminder: {error}"

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