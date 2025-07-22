from .models import db, User, Conversation, Message, UserPreference, Log
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID # Import UUID for type consistency

class ConversationMemory:
    """
    Manages conversation history and context for a user.
    """
    def __init__(self, user_id: uuid.UUID): # user_id is now a UUID object
        self.user_id = user_id
        self.user = User.query.get(user_id) # SQLAlchemy handles UUID objects directly

    def get_recent_conversation_context(self, conversation_id: int, limit: int = 10) -> str:
        """
        Retrieves the last 'limit' messages from a specific conversation.
        """
        conversation = Conversation.query.get(conversation_id)
        # Compare UUID objects directly
        if not conversation or conversation.user_id != self.user_id:
            return ""

        messages = Message.query.filter_by(conversation_id=conversation_id)\
            .order_by(Message.timestamp.desc())\
            .limit(limit).all()

        context = "Recent conversation:\n"
        for msg in reversed(messages):
            context += f"- {msg.message_type.value}: {msg.content}\n"
        return context

    def get_user_preferences_summary(self) -> str:
        """
        Returns a summary of the user's preferences.
        """
        if not self.user:
            return "No user preferences set."

        summary = "User Preferences:\n"
        # Access 'preferences' JSON field directly from User model
        if self.user.preferences:
            for key, value in self.user.preferences.items():
                summary += f"- {key}: {value}\n"
        
        # Include detailed preferences from UserPreference table (if any)
        # Filter by user_id (UUID object)
        detailed_prefs = UserPreference.query.filter_by(user_id=self.user_id).all()
        for pref in detailed_prefs:
            summary += f"- {pref.category}.{pref.key}: {pref.value}\n"

        return summary

    def get_context_for_prompt(self, conversation_id: int, message_limit: int = 10) -> str:
        """
        Constructs a comprehensive context string for the AI prompt.
        """
        context = ""
        
        context += self.get_user_preferences_summary()
        context += "\n"

        context += self.get_recent_conversation_context(conversation_id, limit=message_limit)
        
        return context

class ConversationContext:
    """
    Provides structured context from conversation history.
    """
    def __init__(self, user_id: uuid.UUID, conversation_id: int): # user_id is a UUID object
        self.user_id = user_id
        self.conversation_id = conversation_id

    def get_full_context(self, last_n_messages: int = 10):
        """
        Gathers comprehensive context for a prompt.
        """
        user = User.query.get(self.user_id) # Query User by UUID object
        conversation = Conversation.query.get(self.conversation_id)

        if not user or not conversation:
            return None

        # 1. User Information
        user_info = {
            "name": user.username,
            "role": user.role.value,
            "preferences": user.preferences,
            "timezone": user.timezone,
            "language": user.language,
        }

        # 2. Conversation History
        messages = Message.query.filter_by(conversation_id=self.conversation_id)\
            .order_by(Message.timestamp.desc())\
            .limit(last_n_messages).all()
        
        message_history = []
        for msg in reversed(messages):
            msg_dict = msg.to_dict()
            message_history.append(msg_dict)

        # 3. Conversation Metadata
        conversation_meta = {
            "title": conversation.title,
            "summary": conversation.summary,
            "tags": conversation.tags,
            "started_at": conversation.started_at.isoformat()
        }

        return {
            "user": user_info,
            "conversation_meta": conversation_meta,
            "history": message_history
        }
