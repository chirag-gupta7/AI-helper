"""
API Client for external services used by voice commands.
Handles weather, news, and other third-party API integrations.
"""
import os
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WeatherAPIClient:
    """Client for OpenWeatherMap API integration."""
    
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.base_url = "http://api.openweathermap.org/data/2.5"
        
    def get_current_weather(self, location: str, units: str = "imperial") -> Dict[str, Any]:
        """Get current weather for a location."""
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key not configured")
            
        try:
            url = f"{self.base_url}/weather"
            params = {
                'q': location,
                'appid': self.api_key,
                'units': units
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API request failed: {e}")
            raise
            
    def get_weather_forecast(self, location: str, units: str = "imperial") -> Dict[str, Any]:
        """Get 5-day weather forecast for a location."""
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key not configured")
            
        try:
            url = f"{self.base_url}/forecast"
            params = {
                'q': location,
                'appid': self.api_key,
                'units': units
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather forecast API request failed: {e}")
            raise

class NewsAPIClient:
    """Client for NewsAPI.org integration."""
    
    def __init__(self):
        self.api_key = os.getenv('NEWS_API_KEY')
        self.base_url = "https://newsapi.org/v2"
        
    def get_top_headlines(self, category: str = None, country: str = "us", page_size: int = 5) -> Dict[str, Any]:
        """Get top headlines from NewsAPI."""
        if not self.api_key:
            raise ValueError("News API key not configured")
            
        try:
            url = f"{self.base_url}/top-headlines"
            params = {
                'apiKey': self.api_key,
                'country': country,
                'pageSize': page_size
            }
            
            if category:
                params['category'] = category.lower()
                
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"News API request failed: {e}")
            raise
            
    def search_news(self, query: str, sort_by: str = "publishedAt", page_size: int = 5) -> Dict[str, Any]:
        """Search for news articles by query."""
        if not self.api_key:
            raise ValueError("News API key not configured")
            
        try:
            url = f"{self.base_url}/everything"
            params = {
                'apiKey': self.api_key,
                'q': query,
                'sortBy': sort_by,
                'pageSize': page_size
            }
                
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"News search API request failed: {e}")
            raise

class TaskScheduler:
    """Simple task scheduler for reminders and timers."""
    
    def __init__(self):
        self.scheduled_tasks = {}
        
    def schedule_reminder(self, reminder_id: str, delay_minutes: int, callback_func, *args, **kwargs):
        """Schedule a reminder to execute after delay."""
        import threading
        import time
        
        def execute_reminder():
            time.sleep(delay_minutes * 60)
            try:
                callback_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing reminder {reminder_id}: {e}")
            finally:
                # Clean up
                if reminder_id in self.scheduled_tasks:
                    del self.scheduled_tasks[reminder_id]
        
        thread = threading.Thread(target=execute_reminder, daemon=True)
        self.scheduled_tasks[reminder_id] = {
            'thread': thread,
            'scheduled_at': datetime.utcnow(),
            'delay_minutes': delay_minutes,
            'type': 'reminder'
        }
        thread.start()
        
    def schedule_timer(self, timer_id: str, duration_seconds: int, callback_func, *args, **kwargs):
        """Schedule a timer to execute after duration."""
        import threading
        import time
        
        def execute_timer():
            time.sleep(duration_seconds)
            try:
                callback_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing timer {timer_id}: {e}")
            finally:
                # Clean up
                if timer_id in self.scheduled_tasks:
                    del self.scheduled_tasks[timer_id]
        
        thread = threading.Thread(target=execute_timer, daemon=True)
        self.scheduled_tasks[timer_id] = {
            'thread': thread,
            'scheduled_at': datetime.utcnow(),
            'duration_seconds': duration_seconds,
            'type': 'timer'
        }
        thread.start()
        
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.scheduled_tasks:
            # Note: We can't actually stop a running thread in Python,
            # but we can remove it from our tracking
            del self.scheduled_tasks[task_id]
            return True
        return False
        
    def get_active_tasks(self) -> Dict[str, Any]:
        """Get list of active scheduled tasks."""
        return {tid: {
            'scheduled_at': task_info['scheduled_at'].isoformat(),
            'type': task_info['type'],
            'delay_minutes': task_info.get('delay_minutes'),
            'duration_seconds': task_info.get('duration_seconds')
        } for tid, task_info in self.scheduled_tasks.items()}

# Global instances
weather_client = WeatherAPIClient()
news_client = NewsAPIClient()
task_scheduler = TaskScheduler()

def get_weather_client() -> WeatherAPIClient:
    """Get weather API client instance."""
    return weather_client

def get_news_client() -> NewsAPIClient:
    """Get news API client instance."""
    return news_client

def get_task_scheduler() -> TaskScheduler:
    """Get task scheduler instance."""
    return task_scheduler

import requests
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class VoiceAssistantAPIClient:
    """Python client for the Voice Assistant API"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to the API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return self._make_request('GET', '/health')
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information"""
        return self._make_request('GET', '/api/auth/session')
    
    def get_today_schedule(self) -> Dict[str, Any]:
        """Get today's schedule"""
        return self._make_request('GET', '/api/calendar/today')
    
    def get_upcoming_events(self, days: int = 7) -> Dict[str, Any]:
        """Get upcoming events"""
        return self._make_request('GET', '/api/calendar/upcoming', params={'days': days})
    
    def create_event(self, event_text: str) -> Dict[str, Any]:
        """Create a new calendar event"""
        return self._make_request('POST', '/api/calendar/create', data={'event_text': event_text})
    
    def get_next_meeting(self) -> Dict[str, Any]:
        """Get next meeting"""
        return self._make_request('GET', '/api/calendar/next-meeting')
    
    def get_free_time(self) -> Dict[str, Any]:
        """Get free time today"""
        return self._make_request('GET', '/api/calendar/free-time')
    
    def start_voice_assistant(self) -> Dict[str, Any]:
        """Start voice assistant"""
        return self._make_request('POST', '/api/voice/start')
    
    def stop_voice_assistant(self) -> Dict[str, Any]:
        """Stop voice assistant"""
        return self._make_request('POST', '/api/voice/stop')
    
    def get_voice_status(self) -> Dict[str, Any]:
        """Get voice assistant status"""
        return self._make_request('GET', '/api/voice/status')

# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create client
    client = VoiceAssistantAPIClient()
    
    print("🧪 Testing Voice Assistant API Client - Chirag's Backend")
    print("=" * 60)
    
    # Test health check
    print("\n1. Health Check:")
    health = client.health_check()
    print(f"   Status: {'✅ Healthy' if health.get('success') else '❌ Unhealthy'}")
    if health.get('success'):
        print(f"   Calendar Connected: {health.get('data', {}).get('calendar_connected', 'Unknown')}")
    
    # Test today's schedule
    print("\n2. Today's Schedule:")
    schedule = client.get_today_schedule()
    if schedule.get('success'):
        print(f"   Schedule: {schedule.get('data', {}).get('schedule', 'No schedule')}")
    else:
        print(f"   Error: {schedule.get('error', 'Unknown error')}")
    
    # Test creating an event
    print("\n3. Creating Test Event:")
    event_result = client.create_event("Test API call event tomorrow at 3pm")
    if event_result.get('success'):
        print(f"   Result: {event_result.get('data', {}).get('result', 'Event created')}")
    else:
        print(f"   Error: {event_result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("🎉 API Client Testing Complete!")