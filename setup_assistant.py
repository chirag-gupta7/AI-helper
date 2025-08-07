import os
import sys
import subprocess
import tempfile
import time

def run_command(command, error_message=None):
    """Run a command and return its success status"""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {error_message if error_message else 'Command failed'}")
        print(f"Output: {result.stdout}")
        print(f"Error: {result.stderr}")
        return False
    print(f"Success: {command}")
    return True

def main():
    print("=== Voice Assistant Setup ===")
    print("This script will set up the Voice Assistant dependencies.")
    
    # Clean environment
    print("\n--- Cleaning environment ---")
    run_command("pip uninstall -y flask flask-socketio gevent", "Failed to clean environment")
    run_command("pip cache purge", "Failed to clean pip cache")
    
    # Create a temporary requirements file
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as temp:
        temp.write("""
flask==2.2.3
werkzeug==2.3.7
SQLAlchemy==1.4.52
Flask-SQLAlchemy==3.0.5
flask-migrate==4.0.5
flask-login==0.6.2
Flask-CORS==4.0.0
flask-socketio==5.0.3
python-dotenv==1.0.0
pyttsx3==2.90
elevenlabs==0.2.24
requests==2.31.0
APScheduler==3.10.4
""")
        temp_requirements = temp.name
    
    # Install core packages one by one
    print("\n--- Installing core packages ---")
    packages = [
        "flask==2.2.3",
        "werkzeug==2.3.7",
        "SQLAlchemy==1.4.52",
        "Flask-SQLAlchemy==3.0.5",
        "flask-migrate==4.0.5",
        "flask-login==0.6.2",
        "Flask-CORS==4.0.0",
        "flask-socketio==5.0.3",
        "python-dotenv==1.0.0",
        "pyttsx3==2.90",
        "elevenlabs==0.2.24",
        "requests==2.31.0",
        "APScheduler==3.10.4"
    ]
    
    for package in packages:
        if not run_command(f"pip install {package}", f"Failed to install {package}"):
            print(f"Warning: Failed to install {package}, continuing anyway...")
    
    # Try to install compatible gevent
    print("\n--- Trying to install gevent ---")
    success = run_command("pip install --only-binary :all: gevent>=24.0.0", 
                         "Could not install gevent binary wheel")
    
    if not success:
        print("Warning: Could not install gevent. Will run without it.")
    
    # Create the helper script to run without gevent
    print("\n--- Creating helper scripts ---")
    os.makedirs("backend", exist_ok=True)
    
    with open("backend/run_without_gevent.py", "w", encoding="utf-8") as f:
        f.write('''
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app after environment is loaded
from backend.app import app, socketio

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starting Voice Assistant Backend on {host}:{port}")
    print(f"Debug mode: {app.config.get('DEBUG', False)}")
    
    # Run with standard eventlet instead of gevent
    socketio.run(
        app,
        host=host,
        port=port,
        debug=app.config.get('DEBUG', False),
        use_reloader=False,
        # Skip using gevent
        async_mode='threading'  
    )
''')
    
    with open("backend/socket_fix.py", "w", encoding="utf-8") as f:
        f.write('''
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
''')
    
    # Clean up
    os.unlink(temp_requirements)
    
    print("\n=== Setup Complete ===")
    print("\nTo run your application:")
    print("1. Standard method: python -m backend.app")
    print("2. Alternative method (if gevent fails): python -m backend.run_without_gevent")
    print("\nBefore running, add these lines near the top of your app.py:")
    print("from backend.socket_fix import patch_socketio_emit")
    print("# After creating socketio instance:")
    print("socketio = patch_socketio_emit(socketio)")

if __name__ == "__main__":
    main()