# backend/app.py - Final Corrected Version
import os
import sys
import logging
from flask import Flask, request, jsonify, session, g
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import uuid
import time
import traceback
import threading
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import webbrowser
import queue

# Import configuration and other modules
from .config import config
from .models import db, Log, User
from .auth_service import AuthService, require_auth, optional_auth
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
# Import the new VoiceAssistant class
from .voice_assistant import VoiceAssistant

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

# Flask app setup
app = Flask(__name__, instance_relative_config=True)
app.config.from_object(config['development'])

# Enable CORS for the app
CORS(app)

# Initialize extensions
db.init_app(app)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/day", "50/hour"],
    app=app,
)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def log_to_database(user_id, level, message, conversation_id=None):
    try:
        with app.app_context():
            user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
            new_log = Log(
                user_id=user_id_str,
                level=level,
                message=message,
                conversation_id=conversation_id,
                source='app_backend'
            )
            db.session.add(new_log)
            db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log to database: {e}")
        logger.error(traceback.format_exc())
        try:
            db.session.rollback()
        except Exception as rollback_e:
            logger.error(f"Error during rollback: {rollback_e}")

@app.before_request
def before_request_func():
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

# Global VoiceAssistant instance
voice_assistant = None

def on_voice_log(message, level):
    """Callback to send log messages from the voice thread to the frontend."""
    socketio.emit('log', {'message': message, 'level': level}, namespace='/', broadcast=True)

def on_voice_status_change(status):
    """Callback to send status updates from the voice thread to the frontend."""
    socketio.emit('status_update', {'status': status}, namespace='/', broadcast=True)

def init_voice_assistant():
    """Initializes the global VoiceAssistant instance."""
    global voice_assistant
    if voice_assistant is None:
        voice_assistant = VoiceAssistant(app, on_voice_status_change, on_voice_log, log_to_database)


# --- ROUTES ---
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
            'config_env': os.getenv('FLASK_ENV', 'development'),
        }), 200

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

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
        session_obj = AuthService.create_session(
            user=user,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        if not session_obj:
            return jsonify({'error': 'Failed to create session'}), 500
        session['session_token'] = session_obj.session_token
        session['user_id'] = str(user.id)
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
@app.route('/api/voice/status', methods=['GET'])
@optional_auth
def api_voice_status():
    """Get voice assistant status"""
    user_id = request.current_user.id if hasattr(request, 'current_user') and request.current_user else None
    
    if not voice_assistant:
        return jsonify({'success': True, 'data': {'active': False, 'status': 'inactive', 'user_id': None, 'is_listening': False}})
    
    status_data = voice_assistant.get_status()
    
    return jsonify({'success': True, 'data': status_data})

@app.route('/api/voice/start', methods=['POST'])
@limiter.limit("5 per minute")
@require_auth
def api_start_voice():
    """Start voice assistant"""
    user = request.current_user
    user_id = user.id
    
    if not voice_assistant:
        init_voice_assistant()

    success, message = voice_assistant.start_listening(user_id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 500

@app.route('/api/voice/stop', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
def api_stop_voice():
    """Stop voice assistant"""
    user_id = request.current_user.id
    
    if not voice_assistant or not voice_assistant.is_listening:
        return jsonify({'success': False, 'error': "Voice assistant is not active for this user."}), 400
    
    success, message = voice_assistant.stop_listening()
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 500

@app.route('/api/voice/send-transcript', methods=['POST'])
@require_auth
def api_send_transcript():
    """Endpoint to simulate a user's voice transcript."""
    user_id = request.current_user.id
    if not voice_assistant or not voice_assistant.is_listening or not user_id:
        return jsonify({'success': False, 'error': "Voice assistant is not active or user is not authenticated"}), 400

    data = request.json
    transcript = data.get('transcript', '').strip()
    if not transcript:
        return jsonify({'success': False, 'error': 'Transcript is required'}), 400

    voice_assistant.user_transcript_queue.put(transcript)

    return jsonify({'success': True, 'message': 'Transcript received and queued for processing'})


@app.route('/api/voice/input', methods=['POST'])
@limiter.limit("30 per minute")
@require_auth
def api_voice_input():
    """Process voice/text input for the voice assistant"""
    user_id = request.current_user.id
    
    if not request.is_json:
        return jsonify({'success': False, 'error': "Request must be JSON"}), 400
    
    data = request.json
    text_input = data.get('text', '').strip()
    
    if not text_input:
        return jsonify({'success': False, 'error': "text is required"}), 400
    
    # Check if voice assistant is active for this user
    if user_id not in app.state['voice_sessions'] or not app.state['voice_sessions'][user_id].get('active', False):
        return jsonify({'success': False, 'error': "Voice assistant not active for this session"}), 400
    
    if not voice_assistant.conversation_active or voice_assistant.current_user_id != user_id:
        return jsonify({'success': False, 'error': "Voice assistant session not ready"}), 400
    
    try:
        logger.info(f"Processing voice input from user {user_id}: {text_input}")
        log_to_database(user_id, 'INFO', f"Voice input received: {text_input}")
        
        # Process the voice command
        response = voice_assistant.process_voice_command(text_input)
        
        log_to_database(user_id, 'INFO', f"Voice response sent: {response}")
        
        # Emit to the user's room for real-time updates
        socketio.emit('voice_response', {
            'input': text_input,
            'response': response,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"user_{str(user_id)}")
        
        return jsonify({
            'success': True,
            'data': {
                'input': text_input,
                'response': response
            },
            'message': "Voice input processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error processing voice input: {e}")
        logger.error(traceback.format_exc())
        log_to_database(user_id, 'ERROR', f"Failed to process voice input: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
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
    user_id = request.current_user.id if hasattr(request, 'current_user') and request.current_user else None
    
    if user_id:
        room_name = f"user_{str(user_id)}"
        join_room(room_name)
        logger.info(f"Client connected: {user_id}, joined room: {room_name}")
        log_to_database(user_id, 'INFO', "WebSocket client connected")
    else:
        logger.info("Client connected (unauthenticated)")
        log_to_database(None, 'INFO', "Unauthenticated WebSocket client connected")
    
    emit('log', {'message': 'Connected to server', 'level': 'success'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnect"""
    logger.info('Client disconnected')

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
    
    init_voice_assistant()

    socketio.run(
        app,
        host=host,
        port=port,
        debug=app.config['DEBUG'],
        use_reloader=False
    )
