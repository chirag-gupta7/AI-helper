# backend/auth_service.py - Complete authentication service
from flask import request, session, jsonify, current_app
from functools import wraps
import hashlib
from datetime import datetime, timedelta
import secrets
import re
from .models import db, User, UserSession, APIToken # Ensure models are correctly imported
import logging
import uuid # Ensure uuid is imported

logger = logging.getLogger(__name__)

class AuthService:
    """Complete authentication service"""

    @staticmethod
    def validate_email(email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_password(password):
        """Validate password strength"""
        errors = []

        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")

        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if not re.search(r'\\d', password):
            errors.append("Password must contain at least one digit")

        if not re.search(r'[!@#$%^&*()_+\-=\\[\]{};\':"\\|,.<>\\/?]', password):
            errors.append("Password must contain at least one special character")

        return errors

    @staticmethod
    def register_user(username, email, password, first_name=None, last_name=None):
        """Register a new user with proper validation"""
        try:
            # Validate inputs
            if not username or len(username) < 3:
                return False, "Username must be at least 3 characters long"

            if not AuthService.validate_email(email):
                return False, "Invalid email format"

            password_errors = AuthService.validate_password(password)
            if password_errors:
                return False, "; ".join(password_errors)

            # Check if user already exists
            if User.query.filter_by(username=username).first():
                return False, "Username already exists"

            if User.query.filter_by(email=email).first():
                return False, "Email already registered"

            # Create new user
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            user.set_password(password) # Use the set_password method

            db.session.add(user)
            db.session.commit()

            logger.info(f"New user registered: {username} ({email})")
            return True, user

        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            return False, "Registration failed. Please try again."

    @staticmethod
    def authenticate_user(username_or_email, password):
        """Authenticate user with username/email and password"""
        try:
            # Find user by username or email
            user = User.query.filter(
                (User.username == username_or_email) |
                (User.email == username_or_email)
            ).first()

            if not user:
                return False, "Invalid credentials"

            if not user.is_active:
                return False, "Account is deactivated"

            if not user.check_password(password):
                return False, "Invalid credentials"

            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()

            logger.info(f"User authenticated: {user.username}")
            return True, user

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, "Authentication failed"

    @staticmethod
    def create_session(user, ip_address=None, user_agent=None):
        """Create a new session for authenticated user"""
        try:
            # Cleanup expired sessions (optional, can be done by a background task)
            # AuthService.cleanup_expired_sessions(user.id)

            # Create new session
            session_obj = UserSession.create_session(
                user_id=user.id, # user.id is now a UUID object
                ip_address=ip_address,
                user_agent=user_agent
            )

            db.session.add(session_obj)
            db.session.commit()

            logger.info(f"Session created for user: {user.username}")
            return session_obj

        except Exception as e:
            db.session.rollback()
            logger.error(f"Session creation error: {str(e)}")
            return None

    @staticmethod
    def get_user_from_session(session_token):
        """Get user from session token"""
        try:
            session_obj = UserSession.query.filter_by(
                session_token=session_token,
                is_active=True
            ).first()

            if not session_obj:
                return None

            if session_obj.is_expired():
                session_obj.deactivate()
                db.session.commit()
                return None

            # Update last accessed
            session_obj.last_accessed = datetime.utcnow()
            db.session.commit()

            return session_obj.user

        except Exception as e:
            logger.error(f"Session lookup error: {str(e)}")
            return None

    @staticmethod
    def get_user_from_api_token(token):
        """Get user from API token"""
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            api_token = APIToken.query.filter_by(
                token_hash=token_hash,
                is_active=True
            ).first()

            if not api_token:
                return None

            if api_token.is_expired():
                api_token.is_active = False # Mark as inactive if expired
                db.session.commit()
                return None

            # Update last used
            api_token.update_last_used()
            db.session.commit()

            return api_token.user

        except Exception as e:
            logger.error(f"API token lookup error: {str(e)}")
            return None

    @staticmethod
    def logout_user(session_token):
        """Logout user by deactivating session"""
        try:
            session_obj = UserSession.query.filter_by(
                session_token=session_token
            ).first()

            if session_obj:
                session_obj.deactivate()
                db.session.commit()
                logger.info(f"User logged out: {session_obj.user.username}")
                return True

            return False

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False

    @staticmethod
    def cleanup_expired_sessions(user_id=None):
        """Cleanup expired sessions"""
        try:
            query = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            )

            if user_id:
                query = query.filter_by(user_id=user_id)

            # Deactivate expired sessions
            expired_count = query.update({UserSession.is_active: False})
            db.session.commit()

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")

        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")

# --- START OF CRITICAL FIX: Modified require_auth decorator ---
def require_auth(f):
    """Decorator to require authentication, with a fallback for development."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None

        # Try session-based auth first
        session_token = session.get('session_token')
        if session_token:
            user = AuthService.get_user_from_session(session_token)

        # Try API token auth if session failed
        if not user:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user = AuthService.get_user_from_api_token(token)

        # If still no user and we are in DEBUG mode, create/get a test user
        # This block is often the source of subtle syntax errors due to copy-pasting or manual edits.
        # Ensure indentation and all characters are correct.
        if not user and current_app.config.get('DEBUG'):
            logger.warning("No user authenticated. Using debug fallback user.")
            user = User.query.filter_by(email='testuser@example.com').first()
            if not user:
                logger.info("Creating debug fallback user.")
                # Ensure UUID object is passed, or its string representation if directly assigning to a String column.
                # With the custom UUIDType, passing a uuid.UUID object is now the correct way.
                test_user_uuid = uuid.UUID('00000000-0000-0000-0000-000000000001')
                user = User(id=test_user_uuid, username='testuser', email='testuser@example.com')
                user.set_password('TestPassword123!') # Set password BEFORE adding and committing
                db.session.add(user)
                db.session.commit()
                # After commit, refresh the user object to ensure its ID is correctly loaded
                db.session.refresh(user)


        if not user:
            return jsonify({
                'error': 'Authentication required',
                'code': 'AUTH_REQUIRED'
            }), 401

        # Add user to request context
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function
# --- END OF CRITICAL FIX ---


def require_verified(f):
    """Decorator to require verified user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user.is_verified:
            return jsonify({
                'error': 'Email verification required',
                'code': 'VERIFICATION_REQUIRED'
            }), 403

        return decorated_function

def optional_auth(f):
    """Decorator for optional authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None

        # Try session-based auth first
        session_token = session.get('session_token')
        if session_token:
            user = AuthService.get_user_from_session(session_token)

        # Try API token auth if session failed
        if not user:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user = AuthService.get_user_from_api_token(token)

        # Add user to request context (may be None)
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function