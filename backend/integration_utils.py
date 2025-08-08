"""
Backend Integration Utilities
Provides enhanced error handling, compatibility fixes, and utility functions.
"""
import os
import sys
import logging
import traceback
import uuid
from datetime import datetime, timezone
from flask import g, request, session
from functools import wraps

logger = logging.getLogger(__name__)

def ensure_uuid_compatibility():
    """Ensure UUID handling works consistently across the application."""
    def safe_uuid_convert(value):
        """Safely convert various UUID formats to string."""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, str):
            try:
                # Validate it's a proper UUID
                uuid.UUID(value)
                return value
            except ValueError:
                return None
        return str(value)
    
    return safe_uuid_convert

def enhanced_error_handler(func):
    """Decorator for enhanced error handling in routes."""
    @wraps(func)
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
            
            return {
                'success': False,
                'error': 'Internal server error',
                'message': str(e) if hasattr(e, 'message') else 'An unexpected error occurred'
            }, 500
    
    return wrapper

def safe_database_operation(operation_func):
    """Safely execute database operations with automatic rollback on error."""
    @wraps(operation_func)
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
    user_info = {
        'authenticated': False,
        'user_id': None,
        'session_id': None,
        'user': None
    }
    
    try:
        if hasattr(request, 'current_user') and request.current_user:
            user_info.update({
                'authenticated': True,
                'user_id': str(request.current_user.id),
                'user': request.current_user.to_dict()
            })
        
        user_info['session_id'] = session.get('session_id', str(uuid.uuid4()))
        
    except Exception as e:
        logger.warning(f"Could not get user session info: {e}")
    
    return user_info

def initialize_voice_sessions():
    """Initialize voice session tracking."""
    if not hasattr(g, 'voice_sessions'):
        g.voice_sessions = {}
    return g.voice_sessions

def create_api_response(success=True, data=None, message=None, error=None, status_code=200):
    """Create standardized API responses."""
    response = {
        'success': success,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if error:
        response['error'] = error
        
    return response, status_code

def validate_json_request(required_fields=None):
    """Validate JSON request data."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return create_api_response(
                    success=False,
                    error="Request must be JSON",
                    status_code=400
                )
            
            data = request.get_json()
            if not data:
                return create_api_response(
                    success=False,
                    error="No JSON data provided",
                    status_code=400
                )
            
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in data or not data[field]:
                        missing_fields.append(field)
                
                if missing_fields:
                    return create_api_response(
                        success=False,
                        error=f"Missing required fields: {', '.join(missing_fields)}",
                        status_code=400
                    )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def setup_enhanced_logging():
    """Setup enhanced logging with better formatting."""
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