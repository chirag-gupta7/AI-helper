"""
Flask compatibility patch for newer Flask versions with older Flask-SocketIO
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
            import werkzeug.local
            flask._request_ctx_stack = flask.globals._request_ctx_stack
            
            # Also patch flask_json if needed
            if not hasattr(flask, 'json'):
                import json
                flask.json = json
                
            logger.info("Flask patch applied successfully")
            return True
        else:
            logger.info("Flask patch not needed")
            return False
            
    except Exception as e:
        logger.error(f"Error applying Flask patch: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False