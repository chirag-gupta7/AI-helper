# backend/models.py - Complete database models with proper UUID handling
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, DateTime, Boolean, Text, Integer, TypeDecorator, CHAR
from sqlalchemy.types import Enum as SQLEnum
import secrets
import hashlib
from enum import Enum

# Custom TypeDecorator for UUIDs compatible with SQLAlchemy 1.4
class UUIDType(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            return uuid.UUID(value)
        if isinstance(value, bytes):
            return uuid.UUID(value.decode('utf-8'))
        return value

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

    # Simplified relationships using backref for compatibility
    sessions = db.relationship('UserSession', backref='user', lazy=True, cascade='all, delete-orphan')
    api_tokens = db.relationship('APIToken', backref='user', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('Log', backref='user', lazy=True)
    conversations = db.relationship('Conversation', backref='user', lazy=True)
    notes = db.relationship('Note', backref='user', lazy=True)

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
    status = db.Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)

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
    
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False, index=True)
    session_id = db.Column(String(100), nullable=False, index=True)
    title = db.Column(String(200), nullable=True)
    started_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(DateTime, nullable=True)
    total_messages = db.Column(Integer, default=0, nullable=False)
    status = db.Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    summary = db.Column(Text, nullable=True)
    tags = db.Column(db.JSON, default=lambda: [])
    
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    logs = db.relationship('Log', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')

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

    def __repr__(self):
        return f"<Message {self.id}: {self.message_type.value}>"

class Note(db.Model):
    __tablename__ = 'note'
    
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(Text, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Note {self.id} by User {self.user_id}>'

class Log(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(UUIDType, db.ForeignKey('users.id'), nullable=True, index=True)
    conversation_id = db.Column(Integer, db.ForeignKey('conversation.id'), nullable=True, index=True)
    timestamp = db.Column(DateTime, nullable=False, default=datetime.utcnow)
    level = db.Column(String(20), nullable=False, default='INFO')
    message = db.Column(Text, nullable=False)
    source = db.Column(String(50), nullable=True, default='unknown')
    extra_data = db.Column(db.JSON, default=lambda: {})

    def __repr__(self):
        return f"<Log {self.id} [{self.level}] {self.message[:50]}>"

# Additional models for completeness
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

# Legacy compatibility models
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
