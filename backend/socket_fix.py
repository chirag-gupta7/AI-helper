"""
SocketIO compatibility fixes for Flask-SocketIO.
Enhanced version with better error handling and fallback mechanisms.
"""
import logging
import functools

logger = logging.getLogger(__name__)

def patch_socketio_emit(socketio_instance):
    """
    Patch SocketIO instance for compatibility with newer versions.
    
    Args:
        socketio_instance: The SocketIO instance to patch
        
    Returns:
        The patched SocketIO instance
    """
    try:
        # Store original emit method
        original_emit = socketio_instance.emit
        
        def patched_emit(*args, **kwargs):
            """Patched emit method with better error handling."""
            try:
                return original_emit(*args, **kwargs)
            except Exception as e:
                logger.warning(f"SocketIO emit failed: {e}")
                # Fallback behavior - could log or handle gracefully
                return False
        
        # Apply the patch
        socketio_instance.emit = patched_emit
        logger.info("✅ SocketIO emit method patched successfully")
        
        # Additional compatibility patches
        if hasattr(socketio_instance, 'server'):
            try:
                original_server_emit = socketio_instance.server.emit
                
                def patched_server_emit(*args, **kwargs):
                    """Patched server emit method."""
                    try:
                        return original_server_emit(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"SocketIO server emit failed: {e}")
                        return False
                
                socketio_instance.server.emit = patched_server_emit
                logger.info("✅ SocketIO server emit method patched successfully")
            except Exception as e:
                logger.warning(f"Could not patch server emit: {e}")
        
    except Exception as e:
        logger.error(f"Failed to patch SocketIO: {e}")
    
    return socketio_instance