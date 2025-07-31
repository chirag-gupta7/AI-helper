# backend/app.py - Final Corrected Version
import os
import sys
import logging
from flask import Flask, request, jsonify, session, g # Import g for global request context
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import uuid
import time
import traceback
import threading

# Import configuration
from .config import config

# Import your existing modules
from .google_calendar_integration import (
    get_today_schedule,
    get_upcoming_events,
    create_event_from_conversation,
    get_next_meeting,
    get_free_time_today,
    test_calendar_connection,
    reschedule_event,
    cancel_event,
    find_meeting_slots,
    set_event_reminder
)

# UTF-8 console fix
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def _select_rate_limit_storage():
    url = os.getenv("REDIS_URL")
    if not url:
        logger.warning("No REDIS_URL found; falling back to in-memory rate limit store.")
        return "memory://"
    try:
        import redis
        r = redis.from_url(url, socket_connect_timeout=0.5)
        r.ping()
        logger.info(f"Successfully connected to Redis at {url}")
        return url
    except Exception as e:
        logger.warning(f"Redis unreachable at {url}: {e}; falling back to in-memory rate limit store.")
        return "memory://"

# Flask app setup
app = Flask(__name__, instance_relative_config=True)
app.config.from_object(config['development'])

# Initialize extensions
from .models import db, Log, User
from .auth_service import AuthService, require_auth, optional_auth
from flask_socketio import SocketIO, emit, join_room, leave_room

db.init_app(app)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_select_rate_limit_storage(),
    default_limits=["200/day", "50/hour"],
    app=app,
)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def log_to_database(user_id, level, message, conversation_id=None, commit=True):
    # This function is called from routes, which already have an app context.
    # So, no need to push app context here, it's handled by the request context.
    try:
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        new_log = Log(
            user_id=user_id_str,
            level=level,
            message=message,
            conversation_id=conversation_id,
            source='app_backend'
        )
        db.session.add(new_log)
        if commit:
            db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log to database: {e}")
        logger.error(traceback.format_exc()) # Log traceback for debugging
        try:
            db.session.rollback()
        except Exception as rollback_e:
            logger.error(f"Error during rollback: {rollback_e}")

# --- START OF CRITICAL FIX: Ensure DB is created before first request ---
@app.before_request
def before_request_func():
    # Using a global flag g to ensure this runs only once per application context
    # This is more robust than a simple global variable in some deployment scenarios.
    if not getattr(g, 'db_initialized', False):
        with app.app_context():
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table("users"):
                logger.info("Database tables not found. Creating them now...")
                db.create_all()
                logger.info("Database tables created successfully.")
            else:
                logger.info("Database tables already exist.")
        g.db_initialized = True
# --- END OF CRITICAL FIX ---

# FIX: Import and set the Flask app instance in voice_assistant module
from . import voice_assistant
voice_assistant.set_flask_app(app)


# --- ALL YOUR ROUTES (Authentication, Calendar, Voice, etc.) GO HERE ---
# They remain exactly as they were in the previously provided correct versions.
@app.route('/health', methods=['GET'])
@optional_auth
def health_check():
    """Health check endpoint with optional auth info"""
    try:
        user_info = None
        if hasattr(request, 'current_user') and request.current_user:
            user_info = {
                'id': str(request.current_user.id),
                'username': request.current_user.username,
                'authenticated': True
            }
        else:
            user_info = {'authenticated': False}

        calendar_ok = test_calendar_connection()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'user': user_info,
            'database': 'connected',
            'calendar_connected': calendar_ok,
            'voice_sessions': len(app.state.get('voice_sessions', {})),
            'config_env': os.getenv('FLASK_ENV', 'development'),
        }), 200

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        # Add traceback for better debugging
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Include all your other routes here... (The full code for all routes)
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()

        success, result = AuthService.register_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None
        )

        if not success:
            return jsonify({'error': result}), 400

        user = result
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Registration endpoint error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """User login endpoint"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')

        if not username_or_email or not password:
            return jsonify({'error': 'Username/email and password required'}), 400

        success, result = AuthService.authenticate_user(username_or_email, password)

        if not success:
            return jsonify({'error': result}), 401

        user = result

        # Create session
        session_obj = AuthService.create_session(
            user=user,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )

        if not session_obj:
            return jsonify({'error': 'Failed to create session'}), 500

        # Set session
        session['session_token'] = session_obj.session_token
        session['user_id'] = str(user.id) # Store user.id as string UUID in session
        session.permanent = True

        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'session_token': session_obj.session_token
        }), 200

    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    try:
        session_token = session.get('session_token')

        if session_token:
            AuthService.logout_user(session_token)

        session.clear()

        return jsonify({'message': 'Logout successful'}), 200

    except Exception as e:
        logger.error(f"Logout endpoint error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current user info"""
    try:
        return jsonify({
            'user': request.current_user.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        return jsonify({'error': 'Failed to get user info'}), 500

@app.route('/api/auth/session', methods=['GET'])
@optional_auth
def get_session_info():
    """Get current session information (for testing page)."""
    if hasattr(request, 'current_user') and request.current_user:
        return jsonify({
            'success': True,
            'data': {
                'authenticated': True,
                'user': request.current_user.to_dict()
            }
        }), 200
    else:
        return jsonify({
            'success': True,
            'data': {
                'authenticated': False,
                'user': None
            }
        }), 200

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    try:
        data = request.get_json()

        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not current_password or not new_password:
            return jsonify({'error': 'Current and new passwords required'}), 400

        user = request.current_user

        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400

        password_errors = AuthService.validate_password(new_password)
        if password_errors:
            return jsonify({'error': '; '.join(password_errors)}), 400

        user.set_password(new_password)
        db.session.commit()

        return jsonify({'message': 'Password changed successfully'}), 200

    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({'error': 'Failed to change password'}), 500

@app.route('/')
def index():
    """API root endpoint"""
    return jsonify(
        success=True,
        data={
            'service': 'Voice Assistant Backend',
            'version': '1.0.1',
            'status': 'running',
            'user': 'Chirag Gupta',
            'endpoints': {
                'health': '/health',
                'calendar': '/api/calendar/*',
                'voice': '/api/voice/*',
                'auth': '/api/auth/*',
                'logs': '/api/logs',
                'test_page': '/static/index.html'
            }
        },
        message="🎙️ Voice Assistant Backend API is running!"
    )

@app.route('/api/logs', methods=['GET'])
@require_auth
def get_logs():
    """Get paginated logs for the current user"""
    user_id = request.current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    logs = Log.query.filter_by(user_id=user_id).order_by(Log.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        success=True,
        data={
            'logs': [log.to_dict() for log in logs.items],
            'total': logs.total,
            'page': logs.page,
            'pages': logs.pages
        }
    )

@app.route('/api/calendar/today', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
def api_get_today_schedule():
    """Get today's schedule"""
    user_id = request.current_user.id
    try:
        logger.info(f"User {user_id} requested today's schedule")
        log_to_database(user_id, 'INFO', "Requested today's schedule")
        schedule = get_today_schedule()
        log_to_database(user_id, 'INFO', f"Successfully retrieved today's schedule: {len(schedule) if isinstance(schedule, list) else 'schedule data'} events")
        return jsonify(
            success=True,
            data={'schedule': schedule},
            message="Today's schedule retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting today's schedule: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to retrieve today's schedule: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/calendar/upcoming', methods=['GET'])
@limiter.limit("20 per minute")
@require_auth
def api_get_upcoming_events():
    """Get upcoming events"""
    user_id = request.current_user.id
    days = request.args.get('days', 7, type=int)
    
    if days < 1 or days > 365:
        return jsonify(
            success=False,
            error="Days parameter must be between 1 and 365"
        ), 400
    
    try:
        logger.info(f"User {user_id} requested upcoming events for {days} days")
        log_to_database(user_id, 'INFO', f"Requested upcoming events for {days} days")
        
        events = get_upcoming_events(days)
        
        log_to_database(user_id, 'INFO', f"Successfully retrieved {len(events) if isinstance(events, list) else 'upcoming'} events for {days} days")
        
        return jsonify(
            success=True,
            data={'events': events, 'days': days},
            message=f"Upcoming events for {days} days retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting upcoming events: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to retrieve upcoming events: {str(e)}")
        return jsonify(
            success=False,
            error=str(e)
        ), 500

@app.route('/api/calendar/create', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_create_event():
    """Create a new calendar event"""
    user_id = request.current_user.id
    
    if not request.is_json:
        return jsonify(
            success=False,
            error="Request must be JSON"
        ), 400
    
    data = request.json
    event_text = data.get('event_text', '').strip()
    
    if not event_text:
        return jsonify(
            success=False,
            error="event_text is required"
        ), 400
    
    try:
        logger.info(f"User {user_id} creating event: {event_text}")
        log_to_database(user_id, 'INFO', f"Creating calendar event: {event_text}")
        
        result = create_event_from_conversation(event_text)
        
        log_to_database(user_id, 'INFO', f"Successfully created calendar event: {event_text} - Result: {result}")
        
        socketio.emit('calendar_update', {
            'type': 'event_created',
            'event_text': event_text,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"user_{str(user_id)}") # Convert UUID to string for room name
        
        return jsonify(
            success=True,
            data={'result': result, 'event_text': event_text},
            message="Event created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to create calendar event '{event_text}': {str(e)}")
        return jsonify(
            success=False,
            error=str(e)
        ), 500

@app.route('/api/calendar/next-meeting', methods=['GET'])
@limiter.limit("30 per minute")
@require_auth
def api_get_next_meeting():
    """Get next meeting info"""
    user_id = request.current_user.id
    
    try:
        logger.info(f"User {user_id} requested next meeting")
        log_to_database(user_id, 'INFO', "Requested next meeting information")
        
        meeting = get_next_meeting()
        
        log_to_database(user_id, 'INFO', f"Successfully retrieved next meeting: {meeting.get('summary', 'No meeting') if isinstance(meeting, dict) else 'meeting data'}")
        
        return jsonify(
            success=True,
            data={'meeting': meeting},
            message="Next meeting retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting next meeting: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to retrieve next meeting: {str(e)}")
        return jsonify(
            success=False,
            error=str(e)
        ), 500

@app.route('/api/calendar/free-time', methods=['GET'])
@limiter.limit("20 per minute")
@require_auth
def api_get_free_time():
    """Get free time slots today"""
    user_id = request.current_user.id
    
    try:
        logger.info(f"User {user_id} requested free time")
        log_to_database(user_id, 'INFO', "Requested free time slots")
        
        free_time = get_free_time_today()
        
        log_to_database(user_id, 'INFO', f"Successfully retrieved free time slots: {len(free_time) if isinstance(free_time, list) else 'free time data'} slots")
        
        return jsonify(
            success=True,
            data={'free_time': free_time},
            message="Free time retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting free time: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to retrieve free time: {str(e)}")
        return jsonify(
            success=False,
            error=str(e)
        ), 500

@app.route('/api/calendar/reschedule/<event_id>', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_reschedule_event(event_id):
    """Reschedule an existing event"""
    user_id = request.current_user.id
    if not request.is_json:
        return jsonify(success=False, error="Request must be JSON"), 400
    
    data = request.json
    new_start_time = data.get('new_start_time')
    if not new_start_time:
        return jsonify(success=False, error="new_start_time is required"), 400
        
    try:
        logger.info(f"User {user_id} rescheduling event {event_id} to {new_start_time}")
        log_to_database(user_id, 'INFO', f"Rescheduling event {event_id}")
        
        result = reschedule_event(event_id, new_start_time)
        
        log_to_database(user_id, 'INFO', f"Event {event_id} rescheduled. Result: {result}")
        socketio.emit('calendar_update', {'type': 'event_rescheduled', 'event_id': event_id, 'result': result}, room=f"user_{str(user_id)}")
        
        return jsonify(success=True, data={'result': result}, message="Event rescheduled successfully")
    except Exception as e:
        logger.error(f"Error rescheduling event {event_id}: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to reschedule event {event_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/calendar/cancel/<event_id>', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_cancel_event(event_id):
    """Cancel a calendar event"""
    user_id = request.current_user.id
    try:
        logger.info(f"User {user_id} canceling event {event_id}")
        log_to_database(user_id, 'INFO', f"Canceling event {event_id}")
        
        result = cancel_event(event_id)
        
        log_to_database(user_id, 'INFO', f"Event {event_id} canceled. Result: {result}")
        socketio.emit('calendar_update', {'type': 'event_canceled', 'event_id': event_id, 'result': result}, room=f"user_{str(user_id)}")
        
        return jsonify(success=True, data={'result': result}, message="Event canceled successfully")
    except Exception as e:
        logger.error(f"Error canceling event {event_id}: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to cancel event {event_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/calendar/find-slots', methods=['GET'])
@limiter.limit("15 per minute")
@require_auth
def api_find_meeting_slots():
    """Find available meeting slots"""
    user_id = request.current_user.id
    duration = request.args.get('duration', 30, type=int)
    participants = request.args.get('participants', 'primary')
    days = request.args.get('days', 7, type=int)

    try:
        logger.info(f"User {user_id} finding slots for a {duration}min meeting with {participants}")
        log_to_database(user_id, 'INFO', f"Finding {duration}min meeting slots")
        
        slots = find_meeting_slots(duration, participants, days)
        
        log_to_database(user_id, 'INFO', f"Found {len(slots)} meeting slots.")
        
        return jsonify(success=True, data={'slots': slots}, message="Meeting slots retrieved successfully")
    except Exception as e:
        logger.error(f"Error finding meeting slots: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to find meeting slots: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/calendar/reminders/<event_id>', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_set_event_reminder(event_id):
    """Set a reminder for an event"""
    user_id = request.current_user.id
    if not request.is_json:
        return jsonify(success=False, error="Request must be JSON"), 400
        
    data = request.json
    minutes_before = data.get('minutes_before')
    if not isinstance(minutes_before, int) or minutes_before <= 0:
        return jsonify(success=False, error="minutes_before must be a positive integer"), 400

    try:
        logger.info(f"User {user_id} setting reminder for event {event_id}, {minutes_before} minutes before.")
        log_to_database(user_id, 'INFO', f"Setting reminder for event {event_id}")
        
        result = set_event_reminder(event_id, minutes_before)
        
        log_to_database(user_id, 'INFO', f"Reminder set for event {event_id}. Result: {result}")
        
        return jsonify(success=True, data={'result': result}, message="Reminder set successfully")
    except Exception as e:
        logger.error(f"Error setting reminder for event {event_id}: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to set reminder for event {event_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

# Voice assistant API endpoints
@app.route('/api/voice/start', methods=['POST'])
@limiter.limit("5 per minute")
@require_auth
def api_start_voice():
    """Start voice assistant"""
    user = request.current_user
    user_id = user.id
    
    try:
        if user_id in app.state['voice_sessions'] and app.state['voice_sessions'][user_id].get('active', False):
            return jsonify({'success': False, 'error': "Voice assistant already active for this session"}), 400
        
        logger.info(f"Starting voice assistant for user {user_id}")
        log_to_database(user_id, 'INFO', "Voice assistant started")
        
        session_data = {'user_id': user_id, 'started_at': datetime.utcnow(), 'active': True, 'thread': None}
        app.state['voice_sessions'][user_id] = session_data
        
        def voice_worker():
            # The voice_assistant.start_voice_assistant function now handles app_context internally
            try:
                from .voice_assistant import start_voice_assistant # Import the public function
                socketio.emit('voice_status', {'status': 'started', 'message': 'Voice assistant is now active'}, room=f"user_{str(user_id)}")
                start_voice_assistant(user_id=user_id, app_instance=app) # Pass app instance
            except Exception as e:
                logger.error(f"Voice assistant error in worker: {e}")
                logger.error(traceback.format_exc())
                log_to_database(user_id, 'ERROR', f"Voice assistant error in worker: {str(e)}")
                socketio.emit('voice_error', {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}, room=f"user_{str(user_id)}")
                if user_id in app.state['voice_sessions']:
                    app.state['voice_sessions'][user_id]['active'] = False
        
        thread = threading.Thread(target=voice_worker, daemon=True)
        thread.start()
        session_data['thread'] = thread
        
        return jsonify({'success': True, 'data': {'status': 'started', 'user_id': str(user_id)}, 'message': "Voice assistant started successfully"})
            
    except Exception as e:
        logger.error(f"Error starting voice assistant: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to start voice assistant: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/voice/stop', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_stop_voice():
    """Stop voice assistant"""
    user_id = request.current_user.id
    
    if user_id not in app.state['voice_sessions'] or not app.state['voice_sessions'][user_id].get('active', False):
        return jsonify({'success': False, 'error': "Voice assistant not active for this session"}), 400
    
    try:
        logger.info(f"Stopping voice assistant for user {user_id}")
        log_to_database(user_id, 'INFO', "Voice assistant stopped")
        
        # This flag will be checked by the voice_assistant's internal loop
        voice_assistant.conversation_active = False 
        
        socketio.emit('voice_status', {'status': 'stopped', 'message': 'Voice assistant has been stopped', 'timestamp': datetime.utcnow().isoformat()}, room=f"user_{str(user_id)}")
        
        return jsonify({'success': True, 'data': {'status': 'stopped', 'user_id': str(user_id)}, 'message': "Voice assistant stopped successfully"})
        
    except Exception as e:
        logger.error(f"Error stopping voice assistant: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to stop voice assistant: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/voice/status', methods=['GET'])
@optional_auth
def api_voice_status():
    """Get voice assistant status"""
    user_id = request.current_user.id if hasattr(request, 'current_user') and request.current_user else None
    
    if not user_id:
        return jsonify({'success': True, 'data': {'active': False, 'status': 'inactive', 'user_id': None, 'is_listening': False}})

    session_data = app.state['voice_sessions'].get(user_id, {})
    
    # Check the global conversation_active flag from voice_assistant module
    # This reflects the actual state of the voice session thread
    is_active_globally = voice_assistant.conversation_active and voice_assistant.current_user_id == user_id
    
    if is_active_globally and session_data.get('active', False):
        return jsonify({'success': True, 'data': {'active': True, 'started_at': session_data.get('started_at').isoformat(), 'status': 'active', 'user_id': str(user_id), 'is_listening': True}})
    else:
        return jsonify({'success': True, 'data': {'active': False, 'status': 'inactive', 'user_id': str(user_id), 'is_listening': False}})

# Static file serving routes
@app.route('/static/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

@app.route('/test')
def test_page():
    return app.send_static_file('index.html')

# WebSocket events
@socketio.on('connect')
@optional_auth
def handle_connect():
    """Handle client connection"""
    # user_id is now retrieved from request.current_user, set by optional_auth
    user_id = request.current_user.id if hasattr(request, 'current_user') and request.current_user else None
    
    if user_id:
        # Ensure user_id is a string for room name
        room_name = f"user_{str(user_id)}"
        join_room(room_name)
        logger.info(f"Client connected: {user_id}, joined room: {room_name}")
        log_to_database(user_id, 'INFO', "WebSocket client connected")
    else:
        logger.info("Client connected (unauthenticated)")
        log_to_database(None, 'INFO', "Unauthenticated WebSocket client connected")

    emit('connection_status', {'connected': True, 'user_id': str(user_id) if user_id else None, 'server_time': datetime.utcnow().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    # user_id is retrieved from request.current_user if available, or session
    user_id = request.current_user.id if hasattr(request, 'current_user') and request.current_user else session.get('user_id')
    
    if user_id:
        logger.info(f"Client disconnected: {user_id}")
        log_to_database(user_id, 'INFO', "WebSocket client disconnected")
        
        # Ensure user_id is a string for room name
        room_name = f"user_{str(user_id)}"
        leave_room(room_name)
        
        # Mark voice session inactive if the user disconnects
        if user_id in app.state['voice_sessions']:
            app.state['voice_sessions'][user_id]['active'] = False
            # Also tell the voice_assistant module to stop its session
            if voice_assistant.current_user_id == user_id:
                voice_assistant.conversation_active = False
    else:
        logger.info("Unauthenticated client disconnected.")
        log_to_database(None, 'INFO', "Unauthenticated WebSocket client disconnected")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    logger.error(traceback.format_exc()) # Log traceback for debugging
    return jsonify({'success': False, 'error': "Internal server error. Please check server logs for details."}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'success': False, 'error': f"Rate limit exceeded: {e.description}"}), 429

# Global state management
app.state = {
    'voice_sessions': {}, # Tracks active voice sessions by user_id
    'calendar_cache': {},
    'last_cache_update': None
}

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"🚀 Starting Voice Assistant Backend on {host}:{port}")
    logger.info(f"🔧 Debug mode: {app.config['DEBUG']}")
    logger.info(f"👤 User: Chirag Gupta")

    if app.config['DEBUG'] and not os.environ.get('WERKZEUG_RUN_MAIN'):
        import webbrowser
        time.sleep(1.5)
        webbrowser.open_new_tab(f"http://127.0.0.1:{port}/static/index.html")
        logger.info(f"🌍 Opened browser to http://127.0.0.1:{port}/static/index.html")
    
    socketio.run(
        app,
        host=host,
        port=port,
        debug=app.config['DEBUG'],
        use_reloader=True # Use reloader for development convenience
    )

    logger.info("🎙️ Voice Assistant Backend is running!")
else:
    logger.info("🎙️ Voice Assistant Backend module loaded, ready to serve requests.")
    # This allows the app to be imported without running the server immediately.
    # You can import this module in other parts of your application without executing the Flask app.