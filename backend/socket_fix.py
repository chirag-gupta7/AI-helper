# backend/socket_fix.py
"""
SocketIO compatibility fixes for the voice assistant application.
This module contains patches to ensure SocketIO works properly with the application.
"""

import logging
import functools
import sys

logger = logging.getLogger(__name__)

def patch_socketio_emit(socketio):
    """
    Patch SocketIO emit function to handle encoding issues and improve compatibility.
    
    Args:
        socketio: The SocketIO instance to patch
        
    Returns:
        The patched SocketIO instance
    """
    if not socketio:
        logger.warning("Cannot patch None SocketIO instance")
        return socketio
    
    try:
        # Store the original emit function
        original_emit = socketio.emit
        
        def safe_emit(*args, **kwargs):
            """
            Safe emit wrapper that handles encoding issues.
            """
            try:
                # Clean any string arguments to ensure they're ASCII-safe
                cleaned_args = []
                for arg in args:
                    if isinstance(arg, str):
                        # Remove problematic Unicode characters
                        cleaned_arg = arg.encode('ascii', 'ignore').decode('ascii')
                        cleaned_args.append(cleaned_arg)
                    elif isinstance(arg, dict):
                        # Clean dictionary values
                        cleaned_dict = {}
                        for key, value in arg.items():
                            if isinstance(value, str):
                                cleaned_dict[key] = value.encode('ascii', 'ignore').decode('ascii')
                            else:
                                cleaned_dict[key] = value
                        cleaned_args.append(cleaned_dict)
                    else:
                        cleaned_args.append(arg)
                
                # Clean keyword arguments
                cleaned_kwargs = {}
                for key, value in kwargs.items():
                    if isinstance(value, str):
                        cleaned_kwargs[key] = value.encode('ascii', 'ignore').decode('ascii')
                    else:
                        cleaned_kwargs[key] = value
                
                # Call the original emit with cleaned arguments
                return original_emit(*cleaned_args, **cleaned_kwargs)
                
            except Exception as e:
                logger.error(f"Error in safe_emit: {e}")
                # Fallback to original emit in case of error
                try:
                    return original_emit(*args, **kwargs)
                except Exception as fallback_e:
                    logger.error(f"Fallback emit also failed: {fallback_e}")
                    return None
        
        # Replace the emit method with our safe version
        socketio.emit = safe_emit
        
        logger.info("SocketIO emit function patched successfully")
        return socketio
        
    except Exception as e:
        logger.error(f"Error patching SocketIO: {e}")
        # Return the original socketio instance if patching fails
        return socketio


def clean_message_data(data):
    """
    Clean message data to remove problematic Unicode characters.
    
    Args:
        data: The data to clean (can be string, dict, list, etc.)
        
    Returns:
        Cleaned data
    """
    if isinstance(data, str):
        return data.encode('ascii', 'ignore').decode('ascii')
    elif isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_message_data(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_message_data(item) for item in data]
    else:
        return data
