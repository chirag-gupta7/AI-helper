#!/usr/bin/env python3
"""
Test script for ElevenLabs voice system - Backend version
"""
import os
import sys

# Add the parent directory to the path so we can import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from voice_assistant import test_voice_synthesis, initialize_elevenlabs_agent
except ImportError:
    print("❌ Failed to import voice_assistant module")
    print("Make sure you're running this from the backend directory")
    sys.exit(1)

def main():
    print("🧪 Testing ElevenLabs Voice System")
    print("=" * 50)
    
    # Check environment variables
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")
    
    print(f"API Key: {'✅ SET' if api_key else '❌ NOT SET'}")
    print(f"Voice ID: {voice_id or '❌ NOT SET'}")
    print(f"Agent ID: {'✅ SET' if agent_id else '❌ NOT SET'}")
    print()
    
    # Test agent initialization
    print("🤖 Testing Agent Initialization...")
    try:
        success = initialize_elevenlabs_agent()
        print(f"Agent Init: {'✅ SUCCESS' if success else '❌ FAILED'}")
    except Exception as e:
        print(f"Agent Init: ❌ FAILED - {e}")
        success = False
    print()
    
    # Test voice synthesis
    print("🔊 Testing Voice Synthesis...")
    try:
        voice_success = test_voice_synthesis()
        print(f"Voice Test: {'✅ SUCCESS' if voice_success else '❌ FAILED'}")
    except Exception as e:
        print(f"Voice Test: ❌ FAILED - {e}")
        voice_success = False
    
    print("\n" + "=" * 50)
    if success and voice_success:
        print("🎉 All tests passed! Your ElevenLabs setup is working.")
    else:
        print("❌ Some tests failed. Check your configuration.")
        print("\nNext steps:")
        print("1. Make sure your .env file has ELEVENLABS_API_KEY set")
        print("2. Install missing dependencies: pip install elevenlabs speechrecognition pyaudio pyttsx3")
        print("3. Test API endpoint: curl -X POST http://localhost:5000/api/voice/test")

if __name__ == "__main__":
    main()
