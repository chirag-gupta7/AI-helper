"""
Integration utilities for enhanced error handling and database operations.
Compatible with SQLAlchemy 1.4 and Flask 2.x
"""
import logging
import functools
import traceback
import sys
import uuid
from datetime import datetime, timezone
from flask import jsonify, request, session, g
from werkzeug.exceptions import BadRequest

logger = logging.getLogger(__name__)

def setup_enhanced_logging():
    """Setup enhanced logging configuration with better formatting."""
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    
    # File handler
    file_handler = logging.FileHandler('backend_enhanced.log')
    file_handler.setFormatter(log_format)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
    
    return root_logger

def ensure_uuid_compatibility():
    """Ensure UUID handling works consistently across the application."""
    def convert_uuid_to_string(obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return obj
    
    return convert_uuid_to_string

def enhanced_error_handler(func):
    """Enhanced error handler decorator with improved error tracking."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Try to log to database if possible
            try:
                from .models import db, Log
                user_id = getattr(request, 'current_user', {}).get('id') if hasattr(request, 'current_user') else None
                if user_id:
                    log_entry = Log(
                        user_id=str(user_id),
                        level='ERROR',
                        message=f"Route error in {func.__name__}: {str(e)}",
                        source='backend_integration'
                    )
                    db.session.add(log_entry)
                    db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to log error to database: {db_error}")
            
            return create_api_response(
                success=False,
                error='Internal server error',
                message=str(e) if hasattr(e, 'message') else 'An unexpected error occurred',
                status_code=500
            )
    return wrapper

def safe_database_operation(operation_func):
    """Safely execute database operations with automatic rollback on error."""
    @functools.wraps(operation_func)
    def wrapper(*args, **kwargs):
        try:
            result = operation_func(*args, **kwargs)
            return result
        except Exception as e:
            from .models import db
            try:
                db.session.rollback()
                logger.error(f"Database operation failed, rolled back: {str(e)}")
            except Exception as rollback_error:
                logger.error(f"Rollback also failed: {rollback_error}")
            raise e
    
    return wrapper

def get_user_session_info():
    """Get current user and session information safely."""
    try:
        session_info = {
            'session_id': session.get('session_id', str(uuid.uuid4())),
            'user_id': session.get('user_id'),
            'authenticated': 'user_id' in session,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Store in Flask's g object for request-scoped access
        if not hasattr(g, 'session_info'):
            g.session_info = session_info
            
        return session_info
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        return {
            'session_id': str(uuid.uuid4()),
            'user_id': None,
            'authenticated': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

def initialize_voice_sessions():
    """Initialize voice session tracking."""
    if not hasattr(g, 'voice_session'):
        g.voice_session = {
            'active': False,
            'started_at': None,
            'session_id': str(uuid.uuid4())
        }
    return g.voice_session

def create_api_response(success=True, data=None, message=None, error=None, status_code=200):
    """Create standardized API responses."""
    response = {
        'success': success,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if data is not None:
        response['data'] = data
    if message is not None:
        response['message'] = message
    if error is not None:
        response['error'] = error
    
    return jsonify(response), status_code

def validate_json_request(required_fields=None):
    """Validate JSON request data."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                if not request.is_json:
                    return create_api_response(
                        success=False,
                        error="Request must be JSON",
                        status_code=400
                    )
                
                if required_fields:
                    data = request.get_json()
                    if not data:
                        return create_api_response(
                            success=False,
                            error="Invalid JSON data",
                            status_code=400
                        )
                    
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return create_api_response(
                            success=False,
                            error=f"Missing required fields: {', '.join(missing_fields)}",
                            status_code=400
                        )
                
                return func(*args, **kwargs)
            except BadRequest as e:
                return create_api_response(
                    success=False,
                    error="Invalid request format",
                    message=str(e),
                    status_code=400
                )
            except Exception as e:
                logger.error(f"Request validation error: {e}")
                return create_api_response(
                    success=False,
                    error="Request validation failed",
                    status_code=400
                )
        return wrapper
    return decorator

def log_api_call(endpoint, method, user_id=None, response_time=None, status_code=200):
    """Log API calls for monitoring and analytics."""
    try:
        from .models import db, APIUsage
        
        api_usage = APIUsage(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            response_time_ms=response_time,
            status_code=status_code,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(api_usage)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log API call: {e}")

def handle_database_error(func):
    """Decorator to handle database-specific errors gracefully."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            from .models import db
            try:
                db.session.rollback()
            except Exception:
                pass
            
            error_message = str(e)
            if "UNIQUE constraint failed" in error_message:
                return create_api_response(
                    success=False,
                    error="Duplicate entry",
                    message="The requested operation would create a duplicate entry",
                    status_code=409
                )
            elif "FOREIGN KEY constraint failed" in error_message:
                return create_api_response(
                    success=False,
                    error="Invalid reference",
                    message="The operation references non-existent data",
                    status_code=400
                )
            else:
                logger.error(f"Database error in {func.__name__}: {e}")
                return create_api_response(
                    success=False,
                    error="Database error",
                    message="An error occurred while accessing the database",
                    status_code=500
                )
    return wrapper

def format_datetime_for_api(dt):
    """Format datetime objects for API responses."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)

def parse_uuid_safely(uuid_str):
    """Safely parse UUID strings."""
    try:
        if isinstance(uuid_str, uuid.UUID):
            return uuid_str
        if isinstance(uuid_str, str):
            return uuid.UUID(uuid_str)
        return None
    except (ValueError, TypeError):
        return None