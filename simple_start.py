#!/usr/bin/env python3
"""
Simple startup script for the Voice Assistant Backend.
This script provides better error handling and debugging.
"""

import os
import sys
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Setup clean logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

def start_app():
    """Start the application with better error handling."""
    logger = setup_logging()
    logger.info("🚀 Starting Voice Assistant Backend...")
    
    try:
        # Import and apply patches first
        logger.info("Applying compatibility patches...")
        from backend.flask_patch import apply_flask_patches
        apply_flask_patches()
        
        # Import Flask components
        logger.info("Importing Flask components...")
        from flask import Flask
        from flask_cors import CORS
        
        # Create basic Flask app
        logger.info("Creating Flask application...")
        app = Flask(__name__)
        
        # Basic configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
        app.config['DEBUG'] = True
        
        # Enable CORS
        CORS(app, origins="*")
        
        # Add basic routes
        @app.route('/')
        def index():
            return {
                'service': 'Voice Assistant Backend',
                'version': '1.0.1',
                'status': 'running',
                'message': '🎙️ Voice Assistant Backend API is running!'
            }
        
        @app.route('/health')
        def health():
            import time
            return {'status': 'ok', 'timestamp': str(time.time())}
        
        # Try to import SocketIO
        try:
            logger.info("Setting up SocketIO...")
            from flask_socketio import SocketIO
            from backend.socket_fix import patch_socketio_emit
            
            socketio = SocketIO(
                app, 
                cors_allowed_origins="*", 
                async_mode='threading',
                logger=False,
                engineio_logger=False
            )
            
            # Apply socket patches
            socketio = patch_socketio_emit(socketio)
            
            @socketio.on('connect')
            def handle_connect():
                logger.info('Client connected to SocketIO')
            
            logger.info("SocketIO configured successfully")
            use_socketio = True
            
        except Exception as e:
            logger.warning(f"SocketIO setup failed: {e}")
            logger.info("Continuing with basic Flask app...")
            socketio = None
            use_socketio = False
        
        # Start the server
        host = os.getenv('HOST', '127.0.0.1')
        port = int(os.getenv('PORT', 5000))
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Clean up any problematic environment variables before starting
        problematic_vars = ['WERKZEUG_SERVER_FD', 'WERKZEUG_RUN_MAIN']
        for var in problematic_vars:
            if var in os.environ:
                del os.environ[var]
        
        if use_socketio and socketio:
            logger.info("Starting with SocketIO support...")
            try:
                socketio.run(
                    app,
                    host=host,
                    port=port,
                    debug=False,
                    use_reloader=False,
                    allow_unsafe_werkzeug=True
                )
            except Exception as e:
                logger.error(f"SocketIO server failed: {e}")
                logger.info("Falling back to basic Flask server...")
                app.run(
                    host=host,
                    port=port,
                    debug=False,
                    use_reloader=False,
                    threaded=True
                )
        else:
            logger.info("Starting basic Flask server...")
            app.run(
                host=host,
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
            
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    start_app()
