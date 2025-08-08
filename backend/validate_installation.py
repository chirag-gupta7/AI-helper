#!/usr/bin/env python3
"""
Installation validation script for AI-helper dependencies.
Run this after installing requirements to verify everything works correctly.
"""

def test_basic_dependencies():
    """Test basic Flask app dependencies."""
    print("Testing basic dependencies...")
    
    try:
        import flask
        print(f"✅ Flask {flask.__version__}")
    except ImportError as e:
        print(f"❌ Flask import failed: {e}")
        return False
        
    try:
        import requests
        print(f"✅ requests {requests.__version__}")
    except ImportError as e:
        print(f"❌ requests import failed: {e}")
        return False
        
    try:
        from packaging import version
        if version.parse(requests.__version__) >= version.parse("2.32.3"):
            print(f"✅ requests version >= 2.32.3")
        else:
            print(f"⚠️  requests version {requests.__version__} < 2.32.3 (may cause issues with exa-py)")
    except Exception as e:
        print(f"⚠️  Could not verify requests version: {e}")
    
    try:
        import gevent
        print(f"✅ gevent {gevent.__version__}")
    except ImportError as e:
        print(f"❌ gevent import failed: {e}")
        return False
        
    return True

def test_optional_dependencies():
    """Test optional dependencies like exa-py."""
    print("\nTesting optional dependencies...")
    
    try:
        import httpx
        print(f"✅ httpx {httpx.__version__}")
        
        from packaging import version
        if version.parse(httpx.__version__) >= version.parse("0.28.1"):
            print(f"✅ httpx version >= 0.28.1")
        else:
            print(f"⚠️  httpx version {httpx.__version__} < 0.28.1 (required for exa-py)")
            
    except ImportError:
        print("ℹ️  httpx not installed (optional - needed for exa-py)")
    
    try:
        import exa_py
        print(f"✅ exa-py {exa_py.__version__}")
    except ImportError:
        print("ℹ️  exa-py not installed (optional)")
    except Exception as e:
        print(f"⚠️  exa-py import issue: {e}")

def test_flask_app_creation():
    """Test that a basic Flask app can be created."""
    print("\nTesting Flask app creation...")
    
    try:
        from flask import Flask
        app = Flask(__name__)
        
        @app.route('/test')
        def test():
            return "OK"
            
        print("✅ Flask app creation successful")
        return True
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("AI-helper Dependency Validation")
    print("=" * 35)
    
    success = True
    success = test_basic_dependencies() and success
    test_optional_dependencies()  # Optional deps don't affect success
    success = test_flask_app_creation() and success
    
    print("\n" + "=" * 35)
    if success:
        print("🎉 All core dependencies validated successfully!")
        print("The AI-helper backend should work correctly.")
    else:
        print("❌ Some core dependencies failed validation.")
        print("Please check the installation and try again.")
    
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())