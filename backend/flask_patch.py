# backend/flask_patch.py
"""
Flask compatibility patches for the voice assistant application.
This module contains patches to ensure Flask works properly with the application.
"""

import logging
import sys
import os

logger = logging.getLogger(__name__)

def apply_flask_patches():
    """
    Apply Flask compatibility patches.
    This function is called before Flask is imported to ensure compatibility.
    """
    try:
        # Patch 1: Ensure proper UTF-8 encoding for console output
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
                sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not reconfigure stdout/stderr encoding: {e}")
        
        # Patch 2: Set environment variables for Flask compatibility
        if not os.environ.get('FLASK_ENV'):
            os.environ['FLASK_ENV'] = 'development'
        
        # Patch 3: Fix Werkzeug development server issues
        # Remove problematic environment variables that cause KeyError
        werkzeug_vars_to_remove = [
            'WERKZEUG_SERVER_FD',
            'WERKZEUG_RUN_MAIN'
        ]
        for var in werkzeug_vars_to_remove:
            if var in os.environ:
                del os.environ[var]
        
        # Set safe Werkzeug variables
        os.environ['WERKZEUG_RUN_MAIN'] = 'true'
        
        # Patch 4: Set proper locale for Unicode handling
        try:
            import locale
            locale.setlocale(locale.LC_ALL, '')
        except Exception as e:
            logger.warning(f"Could not set locale: {e}")
        
        # Patch 5: Disable Flask reloader to prevent server issues
        os.environ['FLASK_DEBUG'] = '0'
        
        logger.info("Flask compatibility patches applied successfully")
        
    except Exception as e:
        logger.error(f"Error applying Flask patches: {e}")
        # Don't raise the exception to prevent startup failure
