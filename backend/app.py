from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
import threading
import time
from datetime import datetime
import uuid
import traceback

# Import configuration
from config import config

# Import your existing modules
from google_calendar_integration import (
    get_today_schedule, 
    get_upcoming_events,
    create_event_from_conversation,
    get_next_meeting,
    get_free_time_today,
    test_calendar_connection
)

# Configure logging
def setup_logging():
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO'))
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('backend.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Validate environment variables
    try:
        config[config_name].validate_required_env_vars()
        logger.info("✅ All required environment variables are set")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        # For development, continue without validation
        if config_name == 'development':
            logger.warning("⚠️  Continuing in development mode without required env vars")
        else:
            raise
    
    # Initialize extensions
    CORS(app, origins=app.config['ALLOWED_ORIGINS'])
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Rate limiting
    limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
    )
    limiter.init_app(app)
    
    # Global state management
    app.state = {
        'voice_sessions': {},
        'calendar_cache': {},
        'last_cache_update': None
    }
    
    # Helper functions
    def create_response(success=True, data=None, error=None, message=None):
        """Create standardized API response"""
        response = {
            'success': success,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        if data is not None:
            response['data'] = data
        if error:
            response['error'] = error
        if message:
            response['message'] = message
            
        return jsonify(response)
    
    def require_auth():
        """Simple authentication check"""
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        return session['user_id']
    
    # Routes
    @app.route('/')
    def index():
        """API root endpoint"""
        return create_response(
            success=True,
            data={
                'service': 'Voice Assistant Backend',
                'version': '1.0.0',
                'status': 'running',
                'user': 'Chirag Gupta',
                'endpoints': {
                    'health': '/health',
                    'calendar': '/api/calendar/*',
                    'voice': '/api/voice/*',
                    'auth': '/api/auth/*',
                    'test_page': '/static/index.html'
                }
            },
            message="🎙️ Voice Assistant Backend API is running!"
        )
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            # Test calendar connection
            calendar_ok = test_calendar_connection()
            
            return create_response(
                success=True,
                data={
                    'status': 'healthy',
                    'calendar_connected': calendar_ok,
                    'voice_sessions': len(app.state['voice_sessions']),
                    'server_time': datetime.utcnow().isoformat(),
                    'config_env': os.getenv('FLASK_ENV', 'development'),
                    'user': 'Chirag Gupta'
                }
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    # Authentication endpoints
    @app.route('/api/auth/session', methods=['GET'])
    def get_session():
        """Get current session info"""
        user_id = require_auth()
        return create_response(
            success=True,
            data={
                'user_id': user_id,
                'session_active': True,
                'voice_active': user_id in app.state['voice_sessions'],
                'user_name': 'Chirag'
            }
        )
    
    # Calendar API endpoints
    @app.route('/api/calendar/today', methods=['GET'])
    @limiter.limit("30 per minute")
    def api_get_today_schedule():
        """Get today's schedule"""
        user_id = require_auth()
        
        try:
            logger.info(f"User {user_id} requested today's schedule")
            schedule = get_today_schedule()
            
            return create_response(
                success=True,
                data={'schedule': schedule},
                message="Today's schedule retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error getting today's schedule: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/calendar/upcoming', methods=['GET'])
    @limiter.limit("20 per minute")
    def api_get_upcoming_events():
        """Get upcoming events"""
        user_id = require_auth()
        days = request.args.get('days', 7, type=int)
        
        # Validate days parameter
        if days < 1 or days > 365:
            return create_response(
                success=False,
                error="Days parameter must be between 1 and 365"
            ), 400
        
        try:
            logger.info(f"User {user_id} requested upcoming events for {days} days")
            events = get_upcoming_events(days)
            
            return create_response(
                success=True,
                data={'events': events, 'days': days},
                message=f"Upcoming events for {days} days retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/calendar/create', methods=['POST'])
    @limiter.limit("10 per minute")
    def api_create_event():
        """Create a new calendar event"""
        user_id = require_auth()
        
        if not request.is_json:
            return create_response(
                success=False,
                error="Request must be JSON"
            ), 400
        
        data = request.json
        event_text = data.get('event_text', '').strip()
        
        if not event_text:
            return create_response(
                success=False,
                error="event_text is required"
            ), 400
        
        try:
            logger.info(f"User {user_id} creating event: {event_text}")
            result = create_event_from_conversation(event_text)
            
            # Emit real-time update to connected clients
            socketio.emit('calendar_update', {
                'type': 'event_created',
                'event_text': event_text,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }, room=f"user_{user_id}")
            
            return create_response(
                success=True,
                data={'result': result, 'event_text': event_text},
                message="Event created successfully"
            )
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/calendar/next-meeting', methods=['GET'])
    @limiter.limit("30 per minute")
    def api_get_next_meeting():
        """Get next meeting info"""
        user_id = require_auth()
        
        try:
            logger.info(f"User {user_id} requested next meeting")
            meeting = get_next_meeting()
            
            return create_response(
                success=True,
                data={'meeting': meeting},
                message="Next meeting retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error getting next meeting: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/calendar/free-time', methods=['GET'])
    @limiter.limit("20 per minute")
    def api_get_free_time():
        """Get free time slots today"""
        user_id = require_auth()
        
        try:
            logger.info(f"User {user_id} requested free time")
            free_time = get_free_time_today()
            
            return create_response(
                success=True,
                data={'free_time': free_time},
                message="Free time retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error getting free time: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    # Voice assistant API endpoints
    @app.route('/api/voice/start', methods=['POST'])
    @limiter.limit("5 per minute")
    def api_start_voice():
        """Start voice assistant"""
        user_id = require_auth()
        
        if user_id in app.state['voice_sessions']:
            return create_response(
                success=False,
                error="Voice assistant already active for this session"
            ), 400
        
        try:
            logger.info(f"Starting voice assistant for user {user_id}")
            
            # Create voice session
            session_data = {
                'user_id': user_id,
                'started_at': datetime.utcnow(),
                'active': True,
                'thread': None
            }
            
            app.state['voice_sessions'][user_id] = session_data
            
            # Start voice assistant in background thread
            def voice_worker():
                try:
                    # Import and start your voice assistant
                    from voice_assistant import start_voice_assistant
                    
                    # Emit startup message
                    socketio.emit('voice_status', {
                        'status': 'started',
                        'message': 'Voice assistant is now active'
                    }, room=f"user_{user_id}")
                    
                    # Start the actual voice assistant
                    start_voice_assistant()
                    
                except Exception as e:
                    logger.error(f"Voice assistant error: {e}")
                    logger.error(traceback.format_exc())
                    socketio.emit('voice_error', {
                        'error': str(e),
                        'timestamp': datetime.utcnow().isoformat()
                    }, room=f"user_{user_id}")
                finally:
                    # Clean up session
                    if user_id in app.state['voice_sessions']:
                        del app.state['voice_sessions'][user_id]
            
            thread = threading.Thread(target=voice_worker, daemon=True)
            thread.start()
            session_data['thread'] = thread
            
            return create_response(
                success=True,
                data={'status': 'started', 'user_id': user_id},
                message="Voice assistant started successfully"
            )
            
        except Exception as e:
            logger.error(f"Error starting voice assistant: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/voice/stop', methods=['POST'])
    @limiter.limit("10 per minute")
    def api_stop_voice():
        """Stop voice assistant"""
        user_id = require_auth()
        
        if user_id not in app.state['voice_sessions']:
            return create_response(
                success=False,
                error="Voice assistant not active for this session"
            ), 400
        
        try:
            logger.info(f"Stopping voice assistant for user {user_id}")
            
            # Stop the session
            app.state['voice_sessions'][user_id]['active'] = False
            
            # Emit status update
            socketio.emit('voice_status', {
                'status': 'stopped',
                'message': 'Voice assistant has been stopped',
                'timestamp': datetime.utcnow().isoformat()
            }, room=f"user_{user_id}")
            
            return create_response(
                success=True,
                data={'status': 'stopped', 'user_id': user_id},
                message="Voice assistant stopped successfully"
            )
            
        except Exception as e:
            logger.error(f"Error stopping voice assistant: {e}")
            logger.error(traceback.format_exc())
            return create_response(
                success=False,
                error=str(e)
            ), 500
    
    @app.route('/api/voice/status', methods=['GET'])
    def api_voice_status():
        """Get voice assistant status"""
        user_id = require_auth()
        
        session_data = app.state['voice_sessions'].get(user_id)
        
        if session_data:
            return create_response(
                success=True,
                data={
                    'active': session_data['active'],
                    'started_at': session_data['started_at'].isoformat(),
                    'status': 'active' if session_data['active'] else 'inactive',
                    'user_id': user_id
                }
            )
        else:
            return create_response(
                success=True,
                data={
                    'active': False,
                    'status': 'inactive',
                    'user_id': user_id
                }
            )
    
    # Static file serving routes
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files"""
        return app.send_static_file(filename)
    
    # Also add a route to serve the test page directly
    @app.route('/test')
    def test_page():
        """Serve the test page"""
        return app.send_static_file('index.html')
    
    # WebSocket events
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        user_id = require_auth()
        join_room(f"user_{user_id}")
        logger.info(f"Client connected: {user_id}")
        
        emit('connection_status', {
            'connected': True,
            'user_id': user_id,
            'server_time': datetime.utcnow().isoformat()
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        user_id = session.get('user_id')
        if user_id:
            logger.info(f"Client disconnected: {user_id}")
            leave_room(f"user_{user_id}")
            
            # Clean up voice session if active
            if user_id in app.state['voice_sessions']:
                app.state['voice_sessions'][user_id]['active'] = False
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return create_response(
            success=False,
            error="Endpoint not found"
        ), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return create_response(
            success=False,
            error="Internal server error"
        ), 500
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return create_response(
            success=False,
            error=f"Rate limit exceeded: {e.description}"
        ), 429
    
    # Return app and socketio for external use
    app.socketio = socketio
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"🚀 Starting Voice Assistant Backend on {host}:{port}")
    logger.info(f"🔧 Debug mode: {app.config['DEBUG']}")
    logger.info(f"👤 User: Chirag Gupta")
    
    app.socketio.run(
        app, 
        host=host, 
        port=port, 
        debug=app.config['DEBUG'],
        use_reloader=False
    )