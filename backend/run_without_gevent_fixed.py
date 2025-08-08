"""
Fixed version of run_without_gevent.py that works with newer Flask versions
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_app():
    """Run the Flask app with the patch applied"""
    try:
        # Add the project root to path if needed
        current_dir = Path(__file__).parent
        project_root = current_dir.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Apply Flask compatibility patch
        from backend.flask_patch import apply_flask_patches
        apply_flask_patches()
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import app after patches are applied
        from backend.app import app, socketio
        
        # Run the app
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"Starting Voice Assistant Backend on {host}:{port}")
        logger.info(f"Debug mode: {app.config.get('DEBUG', False)}")
        
        # Run with threading mode instead of gevent
        socketio.run(
            app,
            host=host,
            port=port,
            debug=app.config.get('DEBUG', False),
            use_reloader=False,
            async_mode='threading'  
        )
        
    except Exception as e:
        logger.error(f"Error running app: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(run_app())