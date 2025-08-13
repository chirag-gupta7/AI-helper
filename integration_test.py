#!/usr/bin/env python3
"""
Simple test script to verify the voice system integration
"""
import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

def test_imports():
    """Test all imports"""
    print("🧪 Testing Imports...")
    
    try:
        from backend.microphone_handler import MicrophoneHandler
        print("✅ MicrophoneHandler imported")
    except Exception as e:
        print(f"❌ MicrophoneHandler import failed: {e}")
        return False
    
    try:
        from backend.voice_assistant import VoiceAssistant, test_voice_synthesis
        print("✅ VoiceAssistant imported")
    except Exception as e:
        print(f"❌ VoiceAssistant import failed: {e}")
        return False
    
    try:
        import backend.app
        print("✅ App imported")
    except Exception as e:
        print(f"❌ App import failed: {e}")
        return False
    
    return True

def test_environment():
    """Test environment variables"""
    print("\n🔧 Testing Environment...")
    
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")
    
    print(f"API Key: {'✅ SET' if api_key else '❌ NOT SET'}")
    print(f"Voice ID: {'✅ SET' if voice_id else '❌ NOT SET'}")
    print(f"Agent ID: {'✅ SET' if agent_id else '❌ NOT SET'}")
    
    return bool(api_key)

def test_dependencies():
    """Test required dependencies"""
    print("\n📦 Testing Dependencies...")
    
    deps = {
        'elevenlabs': '✅',
        'pyttsx3': '✅',
        'speech_recognition': '✅',
        'flask': '✅',
        'flask_socketio': '✅'
    }
    
    for dep in deps:
        try:
            __import__(dep)
            print(f"{dep}: ✅ INSTALLED")
        except ImportError:
            print(f"{dep}: ❌ MISSING")
            deps[dep] = '❌'
    
    return all(status == '✅' for status in deps.values())

def main():
    print("🧪 Voice System Integration Test")
    print("=" * 50)
    
    imports_ok = test_imports()
    env_ok = test_environment()
    deps_ok = test_dependencies()
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY:")
    print(f"Imports: {'✅ PASS' if imports_ok else '❌ FAIL'}")
    print(f"Environment: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"Dependencies: {'✅ PASS' if deps_ok else '❌ FAIL'}")
    
    if imports_ok and env_ok and deps_ok:
        print("\n🎉 ALL TESTS PASSED! Voice system is ready.")
        print("\nNext steps:")
        print("1. Start the app: python backend/app.py")
        print("2. Test API: curl -X POST http://localhost:5000/api/voice/test")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        if not env_ok:
            print("💡 Make sure to set your ELEVENLABS_API_KEY in .env file")

if __name__ == "__main__":
    main()
