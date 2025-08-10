#!/usr/bin/env python3
"""
Test script for ElevenLabs voice system
"""
import os
import sys
sys.path.append('backend')

from backend.voice_assistant import test_voice_synthesis, initialize_elevenlabs_agent

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
    success = initialize_elevenlabs_agent()
    print(f"Agent Init: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print()
    
    # Test voice synthesis
    print("🔊 Testing Voice Synthesis...")
    voice_success = test_voice_synthesis()
    print(f"Voice Test: {'✅ SUCCESS' if voice_success else '❌ FAILED'}")
    
    print("\n" + "=" * 50)
    if success and voice_success:
        print("🎉 All tests passed! Your ElevenLabs setup is working.")
    else:
        print("❌ Some tests failed. Check your configuration.")

if __name__ == "__main__":
    main()
