from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Log(db.Model):
    """Model to store conversation and system logs."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    level = db.Column(db.String(10), nullable=False)  # e.g., INFO, ERROR, USER, AGENT
    message = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Log {self.id} [{self.level}] {self.message[:50]}>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'level': self.level,
            'message': self.message
        }