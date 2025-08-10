# backend/memory.py - Fixed with proper relative imports
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Fix the import to use relative import with leading dot
from .models import db, User, Conversation, Message, Log

logger = logging.getLogger(__name__)

class ConversationContext:
    """
    Maintains context for an ongoing conversation.
    """
    def __init__(self, user_id, conversation_id=None):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.start_time = datetime.utcnow()
        self.last_activity = self.start_time
        self.topics = []
        self.entities = {}
        self.messages = []
        self.sentiment = "neutral"
        self.summary = ""
        
    def update_activity(self):
        self.last_activity = datetime.utcnow()
        
    def add_message(self, role, content):
        timestamp = datetime.utcnow()
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": timestamp
        })
        self.last_activity = timestamp
        
    def add_topic(self, topic):
        if topic not in self.topics:
            self.topics.append(topic)
            
    def add_entity(self, entity_type, entity_value):
        if entity_type not in self.entities:
            self.entities[entity_type] = []
        if entity_value not in self.entities[entity_type]:
            self.entities[entity_type].append(entity_value)
            
    def set_sentiment(self, sentiment):
        self.sentiment = sentiment
        
    def set_summary(self, summary):
        self.summary = summary
        
    def get_duration(self):
        return (self.last_activity - self.start_time).total_seconds()
    
    def is_active(self, timeout_minutes=30):
        return (datetime.utcnow() - self.last_activity).total_seconds() < (timeout_minutes * 60)
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "topics": self.topics,
            "entities": self.entities,
            "messages_count": len(self.messages),
            "sentiment": self.sentiment,
            "summary": self.summary,
            "duration_seconds": self.get_duration()
        }

class ConversationMemory:
    """
    Manages conversation memory storage and retrieval.
    """
    def __init__(self):
        self.active_conversations: Dict[str, ConversationContext] = {}
        self.max_inactive_time = timedelta(minutes=30)
        
    def start_conversation(self, user_id):
        conversation_id = self._create_db_conversation(user_id)
        context = ConversationContext(user_id, conversation_id)
        self.active_conversations[str(user_id)] = context
        return context
    
    def _create_db_conversation(self, user_id) -> Optional[int]:
        """Create a new conversation in the database and return its ID"""
        try:
            conversation = Conversation(
                user_id=user_id,
                session_id=str(datetime.utcnow().timestamp()),
                is_active=True
            )
            db.session.add(conversation)
            db.session.commit()
            logger.info(f"Created new conversation {conversation.id} for user {user_id}")
            return conversation.id
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return None
        
    def get_context(self, user_id) -> Optional[ConversationContext]:
        """Get current conversation context for user"""
        user_id_str = str(user_id)
        
        # Check if there's an active conversation
        if user_id_str in self.active_conversations:
            context = self.active_conversations[user_id_str]
            if context.is_active():
                return context
            else:
                # Context has expired, clean up
                self._end_conversation_in_db(context.conversation_id)
                del self.active_conversations[user_id_str]
                
        # No active conversation found
        return None
    
    def add_message(self, user_id, role, content):
        """Add a message to the conversation context and database"""
        context = self.get_context(user_id)
        if not context:
            context = self.start_conversation(user_id)
            
        # Add to context
        context.add_message(role, content)
        
        # Add to database
        try:
            message_type = "user" if role == "user" else "assistant"
            message = Message(
                conversation_id=context.conversation_id,
                content=content,
                message_type=message_type,
                timestamp=datetime.utcnow()
            )
            db.session.add(message)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to save message to database: {e}")
        
        return context
    
    def end_conversation(self, user_id):
        """End an active conversation"""
        user_id_str = str(user_id)
        if user_id_str in self.active_conversations:
            context = self.active_conversations[user_id_str]
            self._end_conversation_in_db(context.conversation_id)
            del self.active_conversations[user_id_str]
            return True
        return False
    
    def _end_conversation_in_db(self, conversation_id):
        """Mark a conversation as inactive in the database"""
        if not conversation_id:
            return
            
        try:
            conversation = Conversation.query.get(conversation_id)
            if conversation:
                conversation.is_active = False
                conversation.end_time = datetime.utcnow()
                db.session.commit()
                logger.info(f"Ended conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to end conversation in database: {e}")
    
    def cleanup_inactive(self):
        """Clean up inactive conversations"""
        inactive_keys = []
        
        for user_id, context in self.active_conversations.items():
            if not context.is_active():
                self._end_conversation_in_db(context.conversation_id)
                inactive_keys.append(user_id)
                
        for key in inactive_keys:
            del self.active_conversations[key]
            
        return len(inactive_keys)
    
    def get_recent_conversations(self, user_id, limit=5):
        """Get recent conversations for a user from database"""
        try:
            conversations = (Conversation.query
                            .filter_by(user_id=user_id)
                            .order_by(Conversation.start_time.desc())
                            .limit(limit)
                            .all())
            
            return [{
                'id': conv.id,
                'start_time': conv.start_time,
                'end_time': conv.end_time,
                'is_active': conv.is_active,
                'message_count': len(conv.messages)
            } for conv in conversations]
        except Exception as e:
            logger.error(f"Failed to retrieve recent conversations: {e}")
            return []