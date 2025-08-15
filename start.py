#!/usr/bin/env python3
"""
Voice Assistant Startup Script
Simple script to start the voice assistant application
"""
import os
import sys
from pathlib import Path

def main():
    """Main startup function"""
    print("🎙️ Starting Voice Assistant...")
    print("=" * 40)
    
    # Add backend to Python path
    backend_path = Path(__file__).parent / "backend"
    sys.path.insert(0, str(backend_path))
    
    # Set environment
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development'
    
    try:
        # Import and run the application
        from backend.app import app
        
        print("🌐 Flask server starting on http://127.0.0.1:5000")
        print("📱 Open your browser to access the web interface")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 40)
        
        app.run(host='127.0.0.1', port=5000, debug=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Voice Assistant stopped")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip install -r backend/requirements.txt")

if __name__ == "__main__":
    main()
