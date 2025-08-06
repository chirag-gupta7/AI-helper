import logging
import os
import requests
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import current_app, Flask # Import Flask for type hinting
import uuid # FIX: Import the uuid module here
from .models import db, User, Log
logger = logging.getLogger(__name__)

# Global reference to the Flask app instance, to be set by app.py
_flask_app_instance_cp = None

def set_flask_app_for_command_processor(app_instance: Flask):
    """Sets the Flask app instance for use in command processor background tasks."""
    global _flask_app_instance_cp
    _flask_app_instance_cp = app_instance

class VoiceCommandProcessor:
    """
    Enhanced voice command processor with real API integrations.
    Supports weather, news, reminders, timers, notes, and more.
    """
    def __init__(self, user_id: Optional[uuid.UUID] = None): # user_id is now a UUID object
        self.user_id = user_id
        self.commands = {
            'weather': self.get_weather,
            'news': self.get_news,
            'reminder': self.set_reminder,
            'timer': self.set_timer,
            'note': self.take_note,
            'search': self.web_search,
            'translate': self.translate_text,
            'calculate': self.calculate,
            'fact': self.get_random_fact,
            'joke': self.get_joke,
        }
        
        # API Keys from environment
        self.weather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.news_api_key = os.getenv('NEWS_API_KEY')
        
        # Active timers storage
        self.active_timers = {}

    def process_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """
        Process a given command with enhanced error handling and logging.

        Args:
            command (str): The command to process (e.g., 'weather').
            **kwargs: Additional arguments for the command.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the command.
        """
        action = self.commands.get(command)
        if action:
            logger.info(f"Processing command '{command}' for user {self.user_id}")
            
            # Log to database, passing extra_data instead of metadata
            self._log_command_to_database('INFO', f"Processing voice command: {command}", kwargs)
            
            try:
                result = action(**kwargs)
                self._log_command_to_database('INFO', f"Command '{command}' completed successfully", result)
                return result
            except Exception as e:
                error_msg = f"Error processing command '{command}': {str(e)}"
                logger.error(error_msg)
                self._log_command_to_database('ERROR', error_msg, {'error': str(e)})
                return {'success': False, 'error': error_msg, 'user_message': 'Sorry, I encountered an error processing that command.'}
        else:
            error_msg = f"Unknown command: {command}"
            logger.warning(error_msg)
            self._log_command_to_database('WARNING', error_msg, {'command': command})
            return {'success': False, 'error': error_msg, 'user_message': f"I don't recognize the command '{command}'. Try asking for weather, news, or setting a reminder."}

    def _log_command_to_database(self, level: str, message: str, extra_data: Dict = None):
        """Log command events to database, ensuring application context."""
        if _flask_app_instance_cp:
            with _flask_app_instance_cp.app_context():
                try:
                    from models import db, Log
                    new_log = Log(
                        user_id=str(self.user_id) if self.user_id else None,
                        level=level,
                        message=message,
                        source='voice_command_processor',
                        extra_data=extra_data or {}
                    )
                    db.session.add(new_log)
                    db.session.commit()
                except Exception as e:
                    _flask_app_instance_cp.logger.error(f"Failed to log to database from command processor: {e}")
                    try:
                        if db.session.is_active:
                            db.session.rollback()
                    except Exception as rollback_e:
                        _flask_app_instance_cp.logger.error(f"Error during rollback for command processor logging: {rollback_e}")
                finally:
                    # Ensure session is cleaned up after each DB operation
                    try:
                        db.session.remove()
                    except Exception as cleanup_e:
                        _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in command processor log: {cleanup_e}")
        else:
            logger.error("Flask app instance not set for command processor logging. Cannot log to DB.")


    def get_weather(self, location: str = "New York") -> Dict[str, Any]:
        """
        Get the current weather for a location using OpenWeatherMap API.
        """
        logger.info(f"Fetching weather for {location}...")
        
        if not self.weather_api_key:
            return {
                'success': False,
                'error': 'Weather API key not configured',
                'user_message': f"The weather in {location} is currently sunny and 72°F. (Demo mode - configure OPENWEATHER_API_KEY for real data)"
            }
        
        try:
            # OpenWeatherMap Current Weather API
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': location,
                'appid': self.weather_api_key,
                'units': 'imperial'  # For Fahrenheit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            weather_info = {
                'location': f"{data['name']}, {data['sys']['country']}",
                'temperature': f"{round(data['main']['temp'])}°F",
                'feels_like': f"{round(data['main']['feels_like'])}°F",
                'condition': data['weather'][0]['description'].title(),
                'humidity': f"{data['main']['humidity']}%",
                'wind_speed': f"{data['wind']['speed']} mph"
            }
            
            user_message = f"The weather in {weather_info['location']} is {weather_info['condition']} with a temperature of {weather_info['temperature']} (feels like {weather_info['feels_like']}). Humidity is {weather_info['humidity']} and wind speed is {weather_info['wind_speed']}."
            
            return {
                'success': True,
                'data': weather_info,
                'user_message': user_message
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch weather data: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': f"Sorry, I couldn't get the weather for {location} right now. Please try again later."
            }
        except KeyError as e:
            error_msg = f"Unexpected weather API response format: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': f"I received an unexpected response from the weather service. Please try again."
            }

    def get_news(self, category: str = "technology") -> Dict[str, Any]:
        """
        Get the latest news headlines for a category using NewsAPI.
        """
        logger.info(f"Fetching {category} news...")
        
        if not self.news_api_key:
            demo_headlines = {
                'technology': [
                    "AI Assistant Technology Advances with Voice Integration",
                    "New Weather API Integration Improves Smart Home Systems", 
                    "Voice Command Processing Becomes More Accurate"
                ],
                'business': [
                    "Tech Stocks Rise on AI Innovation News",
                    "Smart Assistant Market Expected to Grow 25%",
                    "Weather Data Services See Increased Demand"
                ],
                'general': [
                    "Smart Home Technology Adoption Increases Globally",
                    "Voice Assistants Help Improve Daily Productivity",
                    "API Integration Simplifies Smart Device Control"
                ]
            }
            
            headlines = demo_headlines.get(category.lower(), demo_headlines['general'])
            user_message = f"Here are the latest {category} headlines: " + " • ".join(headlines)
            
            return {
                'success': True,
                'data': {
                    'category': category,
                    'headlines': headlines,
                    'demo_mode': True
                },
                'user_message': user_message + " (Demo mode - configure NEWS_API_KEY for real news)"
            }
        
        try:
            # NewsAPI.org Headlines
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                'apiKey': self.news_api_key,
                'category': category.lower(),
                'country': 'us',
                'pageSize': 5
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'ok':
                raise Exception(f"News API error: {data.get('message', 'Unknown error')}")
            
            headlines = [article['title'] for article in data['articles']]
            user_message = f"Here are the latest {category} headlines: " + " • ".join(headlines)
            
            return {
                'success': True,
                'data': {
                    'category': category,
                    'headlines': headlines,
                    'total_results': data['totalResults']
                },
                'user_message': user_message
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch news: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': f"Sorry, I couldn't get the latest {category} news right now. Please try again later."
            }

    def set_reminder(self, reminder_text: str, remind_in_minutes: int = 15) -> Dict[str, Any]:
        """
        Set a reminder that will be stored in database and logged.
        """
        logger.info(f"Setting reminder: '{reminder_text}' in {remind_in_minutes} minutes.")
        
        if not self.user_id:
            return {
                'success': False,
                'error': 'User not identified.',
                'user_message': 'I need to know who you are to set a reminder.'
            }
        
        if _flask_app_instance_cp:
            with _flask_app_instance_cp.app_context():
                try:
                    from models import db, UserNotification, NotificationLevel
                    
                    # Calculate reminder time
                    remind_at = datetime.utcnow() + timedelta(minutes=remind_in_minutes)
                    
                    # Create notification
                    notification = UserNotification(
                        user_id=self.user_id,
                        title=f"Reminder: {reminder_text}",
                        message=f"You asked me to remind you: {reminder_text}",
                        level=NotificationLevel.INFO,
                        expires_at=remind_at + timedelta(hours=24),
                        extra_info={
                            'type': 'reminder',
                            'reminder_text': reminder_text,
                            'set_at': datetime.utcnow().isoformat(),
                            'remind_at': remind_at.isoformat()
                        }
                    )
                    
                    db.session.add(notification)
                    db.session.commit()
                    
                    # Schedule the reminder (in a real system, you'd use Celery or similar)
                    threading.Thread(
                        target=self._process_reminder,
                        args=(notification.id, remind_in_minutes),
                        daemon=True
                    ).start()
                    
                    user_message = f"I'll remind you to {reminder_text} in {remind_in_minutes} minutes."
                    
                    return {
                        'success': True,
                        'data': {
                            'reminder_id': notification.id,
                            'reminder_text': reminder_text,
                            'remind_in_minutes': remind_in_minutes,
                            'remind_at': remind_at.isoformat()
                        },
                        'user_message': user_message
                    }
                    
                except Exception as e:
                    _flask_app_instance_cp.logger.error(f"Failed to set reminder in command processor: {e}")
                    try:
                        if db.session.is_active:
                            db.session.rollback()
                    except Exception as rollback_e:
                        _flask_app_instance_cp.logger.error(f"Error during rollback for reminder: {rollback_e}")
                    return {
                        'success': False,
                        'error': str(e),
                        'user_message': 'Sorry, I couldn\'t set that reminder. Please try again.'
                    }
                finally:
                    try:
                        db.session.remove()
                    except Exception as cleanup_e:
                        _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in reminder: {cleanup_e}")
        else:
            logger.error("Flask app instance not set for reminder. Cannot set reminder in DB.")
            return {
                'success': False,
                'error': 'Internal error: App context not available.',
                'user_message': 'Sorry, I encountered an internal error. Please try again.'
            }


    def _process_reminder(self, notification_id: int, delay_minutes: int):
        """Process reminder after delay (background thread)."""
        if _flask_app_instance_cp:
            with _flask_app_instance_cp.app_context():
                try:
                    time.sleep(delay_minutes * 60)
                    
                    from models import db, UserNotification
                    notification = UserNotification.query.get(notification_id)
                    if notification and not notification.is_dismissed:
                        notification.extra_info['triggered'] = True
                        notification.extra_info['triggered_at'] = datetime.utcnow().isoformat()
                        db.session.commit()
                        
                        logger.info(f"Reminder triggered: {notification.title}")
                        self._log_command_to_database('INFO', f"Reminder triggered: {notification.title}")
                        
                except Exception as e:
                    logger.error(f"Error processing reminder {notification_id}: {e}")
                finally:
                    try:
                        db.session.remove()
                    except Exception as cleanup_e:
                        _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in reminder processing: {cleanup_e}")
        else:
            logger.error(f"Flask app instance not set for reminder processing. Cannot process reminder {notification_id}.")

    def set_timer(self, duration_seconds: int = 300, timer_name: str = "Timer") -> Dict[str, Any]:
        """
        Set a timer with background processing.
        """
        logger.info(f"Setting a timer '{timer_name}' for {duration_seconds} seconds.")
        
        import uuid
        timer_id = str(uuid.uuid4())
        
        try:
            # Store timer info
            timer_info = {
                'id': timer_id,
                'name': timer_name,
                'duration_seconds': duration_seconds,
                'start_time': datetime.utcnow(),
                'end_time': datetime.utcnow() + timedelta(seconds=duration_seconds),
                'user_id': self.user_id,
                'status': 'running'
            }
            
            self.active_timers[timer_id] = timer_info
            
            # Start timer in background
            threading.Thread(
                target=self._process_timer,
                args=(timer_id,),
                daemon=True
            ).start()
            
            duration_minutes = duration_seconds // 60
            duration_seconds_remainder = duration_seconds % 60
            
            if duration_minutes > 0:
                time_str = f"{duration_minutes} minute{'s' if duration_minutes != 1 else ''}"
                if duration_seconds_remainder > 0:
                    time_str += f" and {duration_seconds_remainder} second{'s' if duration_seconds_remainder != 1 else ''}"
            else:
                time_str = f"{duration_seconds} second{'s' if duration_seconds != 1 else ''}"
            
            user_message = f"Timer '{timer_name}' set for {time_str}. I'll let you know when it's done."
            
            return {
                'success': True,
                'data': {
                    'timer_id': timer_id,
                    'timer_name': timer_name,
                    'duration_seconds': duration_seconds,
                    'status': 'started'
                },
                'user_message': user_message
            }
            
        except Exception as e:
            error_msg = f"Failed to set timer: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': 'Sorry, I couldn\'t set that timer. Please try again.'
            }

    def _process_timer(self, timer_id: str):
        """Process timer in background thread."""
        try:
            timer_info = self.active_timers.get(timer_id)
            if not timer_info:
                return
            
            # Wait for timer duration
            time.sleep(timer_info['duration_seconds'])
            
            # Timer finished
            timer_info['status'] = 'finished'
            timer_info['finished_at'] = datetime.utcnow()
            
            logger.info(f"Timer '{timer_info['name']}' finished!")
            self._log_command_to_database('INFO', f"Timer completed: {timer_info['name']}")
            
            # In a real system, you'd trigger a notification here
            
        except Exception as e:
            logger.error(f"Error processing timer {timer_id}: {e}")
            if timer_id in self.active_timers:
                self.active_timers[timer_id]['status'] = 'error'

    def take_note(self, note_text: str) -> Dict[str, Any]:
        """
        Take a note and save it with enhanced metadata.
        """
        logger.info(f"Taking note for user {self.user_id}: '{note_text}'")
        
        if not self.user_id:
            return {
                'success': False,
                'error': 'User not identified.',
                'user_message': 'I need to know who you are to save a note.'
            }
            
        if _flask_app_instance_cp:
            with _flask_app_instance_cp.app_context():
                try:
                    from models import db, Note
                    new_note = Note(
                        user_id=self.user_id,
                        content=note_text
                    )
                    db.session.add(new_note)
                    db.session.commit()
                    
                    logger.info(f"Note saved successfully with ID {new_note.id}")
                    user_message = f"Note saved: {note_text[:50]}{'...' if len(note_text) > 50 else ''}"
                    
                    return {
                        'success': True,
                        'data': {
                            'note_id': new_note.id,
                            'content': new_note.content,
                            'created_at': new_note.created_at.isoformat(),
                            'message': 'Note saved successfully.'
                        },
                        'user_message': user_message
                    }
                except Exception as e:
                    _flask_app_instance_cp.logger.error(f"Failed to save note to database from command processor: {e}")
                    try:
                        if db.session.is_active:
                            db.session.rollback()
                    except Exception as rollback_e:
                        _flask_app_instance_cp.logger.error(f"Error during rollback for note: {rollback_e}")
                    return {
                        'success': False,
                        'error': str(e),
                        'user_message': 'Sorry, I couldn\'t save that note. Please try again.'
                    }
                finally:
                    try:
                        db.session.remove()
                    except Exception as cleanup_e:
                        _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in note: {cleanup_e}")
        else:
            logger.error("Flask app instance not set for note taking. Cannot save note to DB.")
            return {
                'success': False,
                'error': 'Internal error: App context not available.',
                'user_message': 'Sorry, I encountered an internal error. Please try again.'
            }


    def web_search(self, query: str) -> Dict[str, Any]:
        """
        Perform a web search (placeholder for search API integration).
        """
        logger.info(f"Performing web search for: {query}")
        
        # Demo response (integrate with real search API like Google Custom Search or Bing)
        return {
            'success': True,
            'data': {
                'query': query,
                'results': [
                    f"Search result 1 for '{query}'",
                    f"Search result 2 for '{query}'",
                    f"Search result 3 for '{query}'"
                ]
            },
            'user_message': f"Here are search results for '{query}': (Demo mode - integrate with search API for real results)"
        }

    def translate_text(self, text: str, target_language: str = "Spanish") -> Dict[str, Any]:
        """
        Translate text to another language (placeholder for translation API).
        """
        logger.info(f"Translating '{text}' to {target_language}")
        
        # Demo response (integrate with Google Translate or similar)
        translations = {
            'hello': {'Spanish': 'Hola', 'French': 'Bonjour', 'German': 'Hallo'},
            'goodbye': {'Spanish': 'Adiós', 'French': 'Au revoir', 'German': 'Auf Wiedersehen'},
            'thank you': {'Spanish': 'Gracias', 'French': 'Merci', 'German': 'Danke'}
        }
        
        translated = translations.get(text.lower(), {}).get(target_language, f"[{text} in {target_language}]")
        
        return {
            'success': True,
            'data': {
                'original_text': text,
                'translated_text': translated,
                'target_language': target_language
            },
            'user_message': f"'{text}' in {target_language} is '{translated}' (Demo mode - integrate with translation API for real translations)"
        }

    def calculate(self, expression: str) -> Dict[str, Any]:
        """
        Perform basic calculations safely.
        """
        logger.info(f"Calculating: {expression}")
        
        try:
            # Basic safety check - only allow numbers, operators, and parentheses
            allowed_chars = set('0123456789+-*/().= ')
            if not all(c in allowed_chars for c in expression):
                raise ValueError("Invalid characters in expression")
            
            # Remove equals sign if present
            expression = expression.replace('=', '').strip()
            
            # Use eval safely for basic math (in production, use a proper math parser)
            result = eval(expression, {"__builtins__": {}})
            
            return {
                'success': True,
                'data': {
                    'expression': expression,
                    'result': result
                },
                'user_message': f"{expression} equals {result}"
            }
            
        except Exception as e:
            error_msg = f"Calculation error: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': f"Sorry, I couldn't calculate '{expression}'. Please check the expression and try again."
            }

    def get_random_fact(self) -> Dict[str, Any]:
        """
        Get a random interesting fact.
        """
        facts = [
            "The human brain has about 86 billion neurons.",
            "Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.",
            "A group of flamingos is called a 'flamboyance'.",
            "The shortest war in history was between Britain and Zanzibar on August 27, 1896. Zanzibar surrendered after 38 minutes.",
            "Octopuses have three hearts and blue blood.",
            "The first computer bug was an actual bug - a moth found trapped in a Harvard computer in 1947."
        ]
        
        import random
        fact = random.choice(facts)
        
        return {
            'success': True,
            'data': {'fact': fact},
            'user_message': f"Here's an interesting fact: {fact}"
        }

    def get_joke(self) -> Dict[str, Any]:
        """
        Get a random joke.
        """
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a fake noodle? An impasta!",
            "Why did the math book look so sad? Because it had too many problems!",
            "What do you call a bear with no teeth? A gummy bear!"
        ]
        
        import random
        joke = random.choice(jokes)
        
        return {
            'success': True,
            'data': {'joke': joke},
            'user_message': joke
        }

    def get_active_timers(self) -> Dict[str, Any]:
        """
        Get list of active timers for the current user.
        """
        user_timers = {tid: timer for tid, timer in self.active_timers.items() 
                      if timer.get('user_id') == self.user_id and timer.get('status') == 'running'}
        
        return {
            'success': True,
            'data': {
                'active_timers': list(user_timers.values()),
                'count': len(user_timers)
            },
            'user_message': f"You have {len(user_timers)} active timer{'s' if len(user_timers) != 1 else ''}."
        }
