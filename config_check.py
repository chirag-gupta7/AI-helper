#!/usr/bin/env python3
"""
Configuration Checker for Voice Assistant
Checks if all required configuration is properly set
"""
import os
from dotenv import load_dotenv

def check_configuration():
    """Check if all required configuration is set"""
    print("🔍 Voice Assistant Configuration Check")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check ElevenLabs configuration
    api_key = os.environ.get('ELEVENLABS_API_KEY')
    voice_id = os.environ.get('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
    agent_id = os.environ.get('ELEVENLABS_AGENT_ID')
    
    print(f"✅ ElevenLabs API Key: {'SET' if api_key and len(api_key) > 10 else '❌ NOT SET'}")
    print(f"✅ ElevenLabs Voice ID: {voice_id}")
    print(f"{'✅' if agent_id else '⚠️'} ElevenLabs Agent ID: {'SET' if agent_id else 'NOT SET (optional)'}")
    
    # Check server configuration
    host = os.environ.get('HOST', '0.0.0.0')
    port = os.environ.get('PORT', '5000')
    
    print(f"✅ Host: {host}")
    print(f"✅ Port: {port}")
    
    print("\n" + "=" * 50)
    
    # Recommendations
    issues = []
    if not api_key:
        issues.append("❌ Set ELEVENLABS_API_KEY in your .env file")
    
    if not agent_id:
        issues.append("⚠️ Consider setting ELEVENLABS_AGENT_ID for conversational AI")
    
    if issues:
        print("🔧 Issues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ All configuration looks good!")
    
    return len(issues) == 0

if __name__ == '__main__':
    check_configuration()
