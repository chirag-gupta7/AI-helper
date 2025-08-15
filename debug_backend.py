#!/usr/bin/env python3
"""
Simple test script to debug the backend startup issues.
"""

import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all the imports that might be causing issues."""
    try:
        print("Testing imports...")
        
        # Test basic imports
        print("✓ Testing basic imports...")
        import backend.flask_patch
        import backend.socket_fix
        print("✓ flask_patch and socket_fix imported successfully")
        
        # Apply flask patches
        print("✓ Applying flask patches...")
        backend.flask_patch.apply_flask_patches()
        print("✓ Flask patches applied")
        
        # Test Flask import
        print("✓ Testing Flask import...")
        from flask import Flask
        print("✓ Flask imported successfully")
        
        # Test SocketIO import
        print("✓ Testing SocketIO import...")
        from flask_socketio import SocketIO
        print("✓ SocketIO imported successfully")
        
        # Test creating a simple Flask app
        print("✓ Testing Flask app creation...")
        app = Flask(__name__)
        print("✓ Flask app created successfully")
        
        # Test creating SocketIO
        print("✓ Testing SocketIO creation...")
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
        print("✓ SocketIO created successfully")
        
        # Test socket patch
        print("✓ Testing socket patch...")
        socketio = backend.socket_fix.patch_socketio_emit(socketio)
        print("✓ Socket patch applied successfully")
        
        print("\n🎉 All imports and basic setup working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_server():
    """Test a simple Flask server without all the complexity."""
    try:
        print("\n" + "="*50)
        print("Testing simple Flask server...")
        
        from flask import Flask
        app = Flask(__name__)
        
        @app.route('/')
        def hello():
            return "Hello from Voice Assistant!"
        
        @app.route('/health')
        def health():
            return {"status": "ok", "message": "Simple server running"}
        
        print("✓ Simple Flask app configured")
        print("✓ Starting server on http://localhost:5001")
        
        # Start the server
        app.run(host='localhost', port=5001, debug=False, use_reloader=False)
        
    except Exception as e:
        print(f"❌ Error starting simple server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 Voice Assistant Backend Debug Tool")
    print("=" * 50)
    
    # Test imports first
    if test_imports():
        print("\n✓ Import tests passed!")
        
        # Ask user if they want to test simple server
        try:
            choice = input("\nDo you want to test a simple server? (y/n): ").strip().lower()
            if choice == 'y':
                test_simple_server()
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
    else:
        print("\n❌ Import tests failed!")
        sys.exit(1)
