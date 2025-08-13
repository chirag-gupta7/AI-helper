#!/usr/bin/env python3
"""
Quick integration test for the improved voice assistant
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_elevenlabs_integration():
    """Test ElevenLabs integration"""
    print("🔍 Testing ElevenLabs Integration...")
    
    try:
        from backend.elevenlabs_integration import ElevenLabsService, elevenlabs_available
        print(f"✅ ElevenLabs integration imported successfully")
        print(f"✅ ElevenLabs available: {elevenlabs_available}")
        
        # Create service instance
        service = ElevenLabsService()
        print("✅ ElevenLabsService instance created")
        
        # Check API key
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if api_key:
            print("✅ API key found in environment")
        else:
            print("⚠️ No API key found, but service will use fallback")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_voice_assistant_import():
    """Test voice assistant import"""
    print("\n🔍 Testing Voice Assistant Import...")
    
    try:
        from backend.voice_assistant import generate_speech, initialize_elevenlabs_service
        print("✅ Voice assistant functions imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 AI Helper Voice Assistant - Quick Integration Test")
    print("=" * 60)
    
    tests = [
        test_elevenlabs_integration,
        test_voice_assistant_import,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test error: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Test Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The integration is working.")
    else:
        print(f"⚠️ {total - passed} test(s) failed.")
        
    print("\n📝 Next Steps:")
    print("1. Set ELEVENLABS_API_KEY environment variable for full functionality")
    print("2. Run: cd backend && python app.py")
    print("3. Open frontend: cd frontend && npm run dev")

if __name__ == "__main__":
    main()
