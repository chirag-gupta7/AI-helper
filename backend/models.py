# backend/models.py - Complete database models with proper UUID handling
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
# Removed from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import String, DateTime, Boolean, Text, Integer, Enum as SQLEnum, TypeDecorator, CHAR
import secrets
import hashlib
from enum import Enum

# Custom TypeDecorator for UUIDs to store them as VARCHAR(36) in SQLite
# and convert them to/from uuid.UUID objects in Python.
class UUIDType(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value) # Convert uuid.UUID object to string for storage

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        # Ensure value is a string before passing to uuid.UUID
        if isinstance(value, str):
            return uuid.UUID(value)
        # Handle cases where it might be bytes (e.g., from some DB drivers)
        if isinstance(value, bytes):
            return uuid.UUID(value.decode('utf-8'))
        return value # Should ideally be a string or None


db = SQLAlchemy()

# Define Enums first
class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"

class SessionStatus(Enum):
    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"

class UserRole(Enum):
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"
    DEVELOPER = "developer"

class NotificationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditAction(Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"
    SETTINGS_CHANGE = "settings_change"

class User(db.Model):
    __tablename__ = 'users'

    # Use custom UUIDType
    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    username = db.Column(String(80), unique=True, nullable=False, index=True)
    email = db.Column(String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(String(255), nullable=False)
    first_name = db.Column(String(50), nullable=True)
    last_name = db.Column(String(50), nullable=True)
    is_active = db.Column(Boolean, default=True)
    is_verified = db.Column(Boolean, default=False)
    role = db.Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(DateTime, nullable=True)
    voice_enabled = db.Column(Boolean, default=True)
    preferred_voice = db.Column(String(50), default='alloy')
    timezone = db.Column(String(50), default='UTC')
    language = db.Column(String(10), default='en')
    preferences = db.Column(db.JSON, default=lambda: {})

    sessions = db.relationship('UserSession', back_populates='user', cascade='all, delete-orphan')
    api_tokens = db.relationship('APIToken', back_populates='user', cascade='all, delete-orphan')
    logs = db.relationship('Log', back_populates='user', lazy=True)
    conversations = db.relationship('Conversation', back_populates='user', lazy=True)
    notes = db.relationship('Note', back_populates='user', lazy=True)
    api_usages = db.relationship('APIUsage', back_populates='user', lazy=True)
    user_preferences_detail = db.relationship('UserPreference', back_populates='user', lazy=True)
    notifications = db.relationship('UserNotification', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', back_populates='user', lazy='dynamic')
    owner_shares = db.relationship('ConversationShare', foreign_keys='[ConversationShare.owner_id]', back_populates='owner', lazy=True)
    shared_with_shares = db.relationship('ConversationShare', foreign_keys='[ConversationShare.shared_with_id]', back_populates='shared_with', lazy=True)
    feedback = db.relationship('UserFeedback', back_populates='user', lazy='dynamic')
    system_alerts_created = db.relationship('SystemAlert', back_populates='created_by_user', lazy=True)

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=32)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    def to_dict(self):
        # Ensure ID is converted to string for dictionary representation
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'role': self.role.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'voice_enabled': self.voice_enabled,
            'preferred_voice': self.preferred_voice,
            'timezone': self.timezone,
            'language': self.language,
            'preferences': self.preferences
        }

    def __repr__(self):
        return f'<User {self.username}>'

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(String(255), unique=True, nullable=False, index=True)
    ip_address = db.Column(String(45), nullable=True)
    user_agent = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    expires_at = db.Column(DateTime, nullable=False)
    last_accessed = db.Column(DateTime, default=datetime.utcnow)
    user = db.relationship('User', back_populates='sessions')
    audit_logs = db.relationship('AuditLog', back_populates='session_rel', lazy='dynamic')

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(64)

    @classmethod
    def create_session(cls, user_id, ip_address=None, user_agent=None, expires_in_days=30):
        return cls(
            user_id=user_id,
            session_token=cls.generate_token(),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def deactivate(self):
        self.is_active = False

    def __repr__(self):
        return f'<UserSession {self.id} for User {self.user_id}>'

class APIToken(db.Model):
    __tablename__ = 'api_tokens'
    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(String(255), unique=True, nullable=False, index=True)
    token_name = db.Column(String(100), nullable=False)
    scopes = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, default=True)
    last_used = db.Column(DateTime, nullable=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    expires_at = db.Column(DateTime, nullable=True)
    user = db.relationship('User', back_populates='api_tokens')

    @staticmethod
    def generate_token():
        return f"vai_{secrets.token_urlsafe(32)}"

    @classmethod
    def create_token(cls, user_id, name, scopes=None, expires_in_days=None):
        token = cls.generate_token()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        api_token = cls(user_id=user_id, token_hash=token_hash, token_name=name, scopes=scopes, expires_at=expires_at)
        return api_token, token

    def is_expired(self):
        return self.expires_at and datetime.utcnow() > self.expires_at

    def update_last_used(self):
        self.last_used = datetime.utcnow()

    def __repr__(self):
        return f'<APIToken {self.token_name} for User {self.user_id}>'

class Conversation(db.Model):
    __tablename__ = 'conversation'
    id = db.Column(Integer, primary_key=True) # Keep as Integer, as it's not a UUID
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    session_id = db.Column(String(100), nullable=False, index=True)
    title = db.Column(String(200), nullable=True)
    started_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(DateTime, nullable=True)
    total_messages = db.Column(Integer, default=0, nullable=False)
    status = db.Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    summary = db.Column(Text, nullable=True)
    tags = db.Column(db.JSON, default=lambda: [])
    
    user = db.relationship('User', back_populates='conversations')
    messages = db.relationship('Message', back_populates='conversation', lazy='dynamic', cascade='all, delete-orphan')
    shares = db.relationship('ConversationShare', back_populates='conversation', lazy='dynamic', cascade='all, delete-orphan')
    feedback = db.relationship('UserFeedback', back_populates='conversation', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', back_populates='conversation_rel', lazy='dynamic', cascade='all, delete-orphan', foreign_keys='[AuditLog.conversation_id]')
    
    logs = db.relationship('Log', back_populates='conversation', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Conversation {self.id}: {self.title or 'Untitled'}>"

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(Integer, primary_key=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=False, index=True)
    message_type = db.Column(SQLEnum(MessageType), nullable=False)
    content = db.Column(Text, nullable=False)
    timestamp = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    extra_data = db.Column(db.JSON, default=lambda: {})
    is_edited = db.Column(Boolean, default=False)
    edited_at = db.Column(DateTime, nullable=True)
    conversation = db.relationship('Conversation', back_populates='messages')
    feedback = db.relationship('UserFeedback', back_populates='message', lazy='dynamic')

    def __repr__(self):
        return f"<Message {self.id}: {self.message_type.value}>"

class Note(db.Model):
    __tablename__ = 'note'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(Text, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', back_populates='notes')

    def __repr__(self):
        return f'<Note {self.id} by User {self.user_id}>'

class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=True, index=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=True, index=True)
    timestamp = db.Column(DateTime, nullable=False, default=datetime.utcnow)
    level = db.Column(String(10), nullable=False)
    message = db.Column(Text, nullable=False)
    source = db.Column(String(50), nullable=True)
    extra_data = db.Column(db.JSON, default=lambda: {})
    user = db.relationship('User', back_populates='logs')
    conversation = db.relationship('Conversation', back_populates='logs')

    def __repr__(self):
        return f"<Log {self.id} [{self.level}] {self.message[:50]}>"

class APIUsage(db.Model):
    __tablename__ = 'api_usage'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    endpoint = db.Column(String(100), nullable=False)
    method = db.Column(String(10), nullable=False)
    timestamp = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    response_time_ms = db.Column(db.Float, nullable=True)
    status_code = db.Column(Integer, nullable=True)
    tokens_used = db.Column(Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    credits_used = db.Column(Integer, nullable=False)
    user = db.relationship('User', back_populates='api_usages')

class AssistantCapability(db.Model):
    __tablename__ = 'assistant_capability'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), unique=True, nullable=False)
    description = db.Column(Text, nullable=True)
    is_enabled = db.Column(Boolean, default=True, nullable=False)
    requires_auth = db.Column(Boolean, default=False, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)

class UserPreference(db.Model):
    __tablename__ = 'user_preference'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    category = db.Column(String(50), nullable=False)
    key = db.Column(String(100), nullable=False)
    value = db.Column(db.JSON, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user = db.relationship('User', back_populates='user_preferences_detail')

class SystemMetrics(db.Model):
    __tablename__ = 'system_metrics'
    id = db.Column(Integer, primary_key=True)
    timestamp = db.Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    metric_name = db.Column(String(100), nullable=False, index=True)
    value = db.Column(db.Float, nullable=False)
    metric_details = db.Column(db.JSON, default=lambda: {})

class UserNotification(db.Model):
    __tablename__ = 'user_notification'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(String(200), nullable=False)
    message = db.Column(Text, nullable=False)
    level = db.Column(SQLEnum(NotificationLevel), default=NotificationLevel.INFO, nullable=False)
    is_read = db.Column(Boolean, default=False, nullable=False)
    is_dismissed = db.Column(Boolean, default=False, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(DateTime, nullable=True)
    action_url = db.Column(String(500), nullable=True)
    extra_info = db.Column(db.JSON, default=lambda: {})
    user = db.relationship('User', back_populates='notifications')

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=True, index=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=True, index=True)
    session_id = db.Column(UUIDType, db.ForeignKey('user_sessions.id'), nullable=True, index=True)
    action = db.Column(SQLEnum(AuditAction), nullable=False)
    resource_type = db.Column(String(50), nullable=True)
    resource_id = db.Column(String(100), nullable=True)
    details = db.Column(Text, nullable=True)
    ip_address = db.Column(String(45), nullable=True)
    user_agent = db.Column(Text, nullable=True)
    timestamp = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    success = db.Column(Boolean, default=True, nullable=False)
    error_message = db.Column(Text, nullable=True)
    extra_data = db.Column(db.JSON, default=lambda: {})
    user = db.relationship('User', back_populates='audit_logs')
    conversation_rel = db.relationship('Conversation', back_populates='audit_logs', foreign_keys=[conversation_id])
    session_rel = db.relationship('UserSession', back_populates='audit_logs', foreign_keys=[session_id])

class ConversationShare(db.Model):
    __tablename__ = 'conversation_share'
    id = db.Column(Integer, primary_key=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=False, index=True)
    owner_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    shared_with_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=True, index=True)
    share_token = db.Column(String(64), unique=True, nullable=False, index=True)
    is_public = db.Column(Boolean, default=False, nullable=False)
    can_edit = db.Column(Boolean, default=False, nullable=False)
    expires_at = db.Column(DateTime, nullable=True)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed = db.Column(DateTime, nullable=True)
    access_count = db.Column(Integer, default=0, nullable=False)
    conversation = db.relationship('Conversation', back_populates='shares')
    owner = db.relationship('User', foreign_keys=[owner_id], back_populates='owner_shares')
    shared_with = db.relationship('User', foreign_keys=[shared_with_id], back_populates='shared_with_shares')

    def __init__(self, **kwargs):
        super(ConversationShare, self).__init__(**kwargs)
        if not self.share_token:
            self.share_token = hashlib.sha256(f"{self.conversation_id}{str(self.owner_id)}{datetime.utcnow()}".encode()).hexdigest()

class UserFeedback(db.Model):
    __tablename__ = 'user_feedback'
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=True, index=True)
    message_id = db.Column(Integer, db.ForeignKey('message.id'), nullable=True, index=True)
    feedback_type = db.Column(String(20), nullable=False)
    rating = db.Column(Integer, nullable=True)
    title = db.Column(String(200), nullable=True)
    content = db.Column(Text, nullable=False)
    category = db.Column(String(50), nullable=True)
    is_resolved = db.Column(Boolean, default=False, nullable=False)
    resolution_notes = db.Column(Text, nullable=True)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    additional_info = db.Column(db.JSON, default=lambda: {})
    user = db.relationship('User', back_populates='feedback')
    conversation = db.relationship('Conversation', back_populates='feedback')
    message = db.relationship('Message', back_populates='feedback')

class SystemAlert(db.Model):
    __tablename__ = 'system_alert'
    id = db.Column(Integer, primary_key=True)
    title = db.Column(String(200), nullable=False)
    message = db.Column(Text, nullable=False)
    level = db.Column(SQLEnum(NotificationLevel), default=NotificationLevel.INFO, nullable=False)
    start_time = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(DateTime, nullable=True)
    is_active = db.Column(Boolean, default=True, nullable=False)
    created_by = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=True)
    created_by_user = db.relationship('User', back_populates='system_alerts_created')

class ConversationHistory(db.Model):
    __tablename__ = 'conversation_history_log'
    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(Text, nullable=False)
    response = db.Column(Text, nullable=True)
    message_type = db.Column(String(20), default='text')
    created_at = db.Column(DateTime, default=datetime.utcnow)
    processing_time = db.Column(db.Float, nullable=True)

class UserPreferences(db.Model):
    __tablename__ = 'user_preferences_settings'
    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, unique=True)
    response_style = db.Column(String(20), default='friendly')
    default_reminder_time = db.Column(Integer, default=15)
    auto_transcribe = db.Column(Boolean, default=True)
    notification_email = db.Column(Boolean, default=True)
    notification_push = db.Column(Boolean, default=True)
    daily_summary = db.Column(Boolean, default=False)
    data_retention_days = db.Column(Integer, default=365)
    allow_analytics = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
