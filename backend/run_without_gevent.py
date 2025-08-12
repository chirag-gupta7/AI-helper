
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
