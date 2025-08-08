"""
Flask compatibility patch for newer Flask versions with older Flask-SocketIO
Enhanced version with better error handling and compatibility.
"""
import sys
import logging

logger = logging.getLogger(__name__)

def apply_flask_patches():
    """
    Apply patches to make Flask-SocketIO work with newer Flask versions
    by redirecting imports of deprecated/moved components.
    """
    try:
        import flask
        import flask.globals
        
        # Check if we need to patch (if _request_ctx_stack is not in flask)
        if not hasattr(flask, '_request_ctx_stack'):
            logger.info("Applying Flask compatibility patch for SocketIO")
            
            # Create the attribute in flask module pointing to the correct location
            from werkzeug.local import LocalStack
            flask._request_ctx_stack = LocalStack()
            
            # Ensure flask.globals has _request_ctx_stack
            if hasattr(flask, 'globals'):
                if not hasattr(flask.globals, '_request_ctx_stack'):
                    flask.globals._request_ctx_stack = flask._request_ctx_stack
            
            # Also patch flask_json if needed
            if not hasattr(flask, 'json'):
                import json
                flask.json = json
            
            # Flask-SocketIO compatibility fixes
            try:
                import flask_socketio
                # Patch for newer Flask-SocketIO versions
                if hasattr(flask_socketio, 'SocketIO'):
                    original_init = flask_socketio.SocketIO.__init__
                    
                    def patched_init(self, app=None, **kwargs):
                        # Remove problematic kwargs for newer versions
                        kwargs.pop('async_handlers', None)
                        return original_init(self, app, **kwargs)
                    
                    flask_socketio.SocketIO.__init__ = patched_init
            except ImportError:
                pass
                
            logger.info("✅ Flask compatibility patches applied successfully")
            return True
        else:
            logger.info("Flask patch not needed")
            return False
            
    except Exception as e:
        logger.error(f"Error applying Flask patch: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False