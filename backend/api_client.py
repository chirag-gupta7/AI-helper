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