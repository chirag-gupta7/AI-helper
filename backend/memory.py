import logging # ADDED: Import logging module
from models import db, User, Conversation, Message, UserPreference, Log
from datetime import datetime, timedelta
import uuid
from flask import current_app # Import current_app to potentially use app_context

# Custom TypeDecorator for UUIDs is defined in models.py and imported via db

class ConversationMemory:
    """
    Manages conversation history and context for a user.
    This class is primarily for retrieving specific, filtered contexts.
    """
    def __init__(self, user_id: uuid.UUID):
        self.user_id = user_id
        # Ensure database access is within an app context if this is called outside a request context
        if current_app:
            with current_app.app_context():
                self.user = User.query.get(user_id)
        else:
            # Fallback if no app context is available (should ideally not happen if called correctly)
            self.user = None
            logging.warning("ConversationMemory initialized without Flask app context, user might be None.")


    def get_recent_conversation_context(self, conversation_id: int, limit: int = 10) -> str:
        """
        Retrieves the last 'limit' messages from a specific conversation.
        """
        if current_app:
            with current_app.app_context():
                conversation = Conversation.query.get(conversation_id)
                if not conversation or conversation.user_id != self.user_id:
                    return ""

                messages = Message.query.filter_by(conversation_id=conversation_id)\
                    .order_by(Message.timestamp.desc())\
                    .limit(limit).all()

                context = "Recent conversation:\n"
                for msg in reversed(messages):
                    context += f"- {msg.message_type.value}: {msg.content}\n"
                return context
        else:
            logging.warning("get_recent_conversation_context called without Flask app context.")
            return "Error: No application context for database access."


    def get_user_preferences_summary(self) -> str:
        """
        Returns a summary of the user's preferences.
        """
        if not self.user:
            return "No user preferences set."

        summary = "User Preferences:\n"
        if self.user.preferences:
            for key, value in self.user.preferences.items():
                summary += f"- {key}: {value}\n"
        
        if current_app:
            with current_app.app_context():
                detailed_prefs = UserPreference.query.filter_by(user_id=self.user_id).all()
                for pref in detailed_prefs:
                    summary += f"- {pref.category}.{pref.key}: {pref.value}\n"
        else:
            logging.warning("get_user_preferences_summary called without Flask app context for detailed prefs.")

        return summary

class ConversationContext:
    """
    Provides structured comprehensive context from conversation history and user data.
    """
    def __init__(self, user_id: uuid.UUID, conversation_id: int):
        self.user_id = user_id
        self.conversation_id = conversation_id

    def get_full_context(self, last_n_messages: int = 10):
        """
        Gathers comprehensive context for a prompt, including user info,
        conversation metadata, and recent history.
        """
        if current_app:
            with current_app.app_context():
                user = User.query.get(self.user_id)
                conversation = Conversation.query.get(self.conversation_id)

                if not user or not conversation:
                    return None

                # 1. User Information
                user_info = {
                    "name": user.username,
                    "role": user.role.value,
                    "preferences": user.preferences, # This is the JSON field
                    "timezone": user.timezone,
                    "language": user.language,
                }
                # Add detailed preferences from UserPreference table if available
                detailed_prefs = UserPreference.query.filter_by(user_id=self.user_id).all()
                for pref in detailed_prefs:
                    user_info[f"pref_{pref.category}_{pref.key}"] = pref.value


                # 2. Conversation History
                messages = Message.query.filter_by(conversation_id=self.conversation_id)\
                    .order_by(Message.timestamp.desc())\
                    .limit(last_n_messages).all()
                
                message_history = []
                for msg in reversed(messages):
                    msg_dict = msg.to_dict() # Assuming Message.to_dict() exists and works
                    message_history.append(msg_dict)

                # 3. Conversation Metadata
                conversation_meta = {
                    "title": conversation.title,
                    "summary": conversation.summary,
                    "tags": conversation.tags,
                    "started_at": conversation.started_at.isoformat() if conversation.started_at else None
                }

                return {
                    "user": user_info,
                    "conversation_meta": conversation_meta,
                    "history": message_history
                }
        else:
            logging.warning("get_full_context called without Flask app context.")
            return None # Return None as context cannot be fetched without app context

    def get_context_for_prompt(self, last_n_messages: int = 10) -> str:
        """
        Constructs a comprehensive context string for the AI prompt
        from the structured full context.
        """
        full_context = self.get_full_context(last_n_messages)
        if not full_context:
            return "No context available."

        context_str = "User Profile:\n"
        for key, value in full_context['user'].items():
            context_str += f"- {key}: {value}\n"
        
        context_str += "\nConversation Metadata:\n"
        for key, value in full_context['conversation_meta'].items():
            context_str += f"- {key}: {value}\n"
            
        context_str += "\nConversation History (most recent first):\n"
        if not full_context['history']:
            context_str += "(No recent messages)\n"
        else:
            # Displaying history in chronological order for better context flow
            for msg in full_context['history']:
                context_str += f"- {msg['message_type']}: {msg['content']}\n"
        
        return context_str
