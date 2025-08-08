import logging
import functools

logger = logging.getLogger(__name__)

def patch_socketio_emit(socketio):
    """
    Patches the socketio.emit function to handle different parameter formats
    between socketio versions.
    """
    original_emit = socketio.emit
    
    @functools.wraps(original_emit)
    def wrapped_emit(event, data=None, room=None, **kwargs):
        try:
            # Try with original parameters
            return original_emit(event, data, room=room, **kwargs)
        except TypeError as e:
            logger.warning(f"Socket.IO emit error: {e}")
            try:
                # Try without 'broadcast' parameter if it causes issues
                kwargs.pop('broadcast', None)
                return original_emit(event, data, room=room, **kwargs)
            except Exception as e2:
                logger.error(f"Socket.IO patched emit also failed: {e2}")
                return None
    
    # Replace the original emit with our wrapped version
    socketio.emit = wrapped_emit
    logger.info("Socket.IO emit function patched for compatibility")
    
    return socketio