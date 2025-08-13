#!/usr/bin/env python3
"""
Comprehensive test script for the AI Helper Voice Assistant
This script tests all components including the new ElevenLabs integration
"""

import os
import sys
import logging
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test if all required imports work"""
    logger.info("Testing imports...")
    
    try:
        # Test basic imports
        import flask
        logger.info(f"✓ Flask version: {flask.__version__}")
        
        import flask_socketio
        logger.info(f"✓ Flask-SocketIO version: {flask_socketio.__version__}")
        
        # Test ElevenLabs
        try:
            import elevenlabs
            logger.info(f"✓ ElevenLabs package available")
        except ImportError:
            logger.warning("⚠️ ElevenLabs package not available")
        
        # Test PyAudio
        try:
            import pyaudio
            logger.info(f"✓ PyAudio available")
        except ImportError:
            logger.warning("⚠️ PyAudio not available")
        
        # Test pyttsx3
        try:
            import pyttsx3
            logger.info(f"✓ pyttsx3 available")
        except ImportError:
            logger.warning("⚠️ pyttsx3 not available")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Import test failed: {e}")
        return False

def test_elevenlabs_integration():
    """Test the new ElevenLabs integration"""
    logger.info("Testing ElevenLabs integration...")
    
    try:
        # Change to backend directory
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        
        from backend.elevenlabs_integration import ElevenLabsService, elevenlabs_available
        
        logger.info(f"✓ ElevenLabs integration module imported successfully")
        logger.info(f"✓ ElevenLabs available: {elevenlabs_available}")
        
        # Test service initialization
        service = ElevenLabsService()
        logger.info("✓ ElevenLabsService instance created")
        
        # Check if API key is available
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if api_key:
            logger.info("✓ ElevenLabs API key found in environment")
            # Test initialization
            if elevenlabs_available:
                try:
                    success = service.initialize()
                    if success:
                        logger.info("✅ ElevenLabs service initialization successful!")
                        logger.info(f"✅ Subscription info: {service.subscription_info}")
                        return True
                    else:
                        logger.warning("⚠️ ElevenLabs service initialization failed")
                        return False
                except Exception as e:
                    logger.warning(f"⚠️ ElevenLabs initialization error: {e}")
                    return False
            else:
                logger.warning("⚠️ ElevenLabs package not available for testing")
                return False
        else:
            logger.warning("⚠️ No ElevenLabs API key found")
            return False
            
    except Exception as e:
        logger.error(f"❌ ElevenLabs integration test failed: {e}")
        return False

def test_voice_assistant_module():
    """Test the voice assistant module"""
    logger.info("Testing voice assistant module...")
    
    try:
        # Change to backend directory
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        
        from backend.voice_assistant import VoiceAssistant, initialize_elevenlabs_service
        
        logger.info("✓ Voice assistant module imported successfully")
        
        # Test service initialization
        try:
            success = initialize_elevenlabs_service()
            if success:
                logger.info("✅ ElevenLabs service initialized from voice assistant")
            else:
                logger.warning("⚠️ ElevenLabs service initialization failed")
        except Exception as e:
            logger.warning(f"⚠️ Service initialization error: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Voice assistant module test failed: {e}")
        return False

def test_speech_generation():
    """Test speech generation with fallback"""
    logger.info("Testing speech generation...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / "backend"))
        
        from backend.voice_assistant import generate_speech, initialize_elevenlabs_service
        
        # Initialize service
        initialize_elevenlabs_service()
        
        # Test speech generation
        test_text = "Hello, this is a test of the voice assistant system."
        logger.info(f"Testing speech with text: {test_text}")
        
        success = generate_speech(test_text)
        if success:
            logger.info("✅ Speech generation successful!")
            return True
        else:
            logger.warning("⚠️ Speech generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Speech generation test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🧪 Starting AI Helper Voice Assistant Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("ElevenLabs Integration Test", test_elevenlabs_integration),
        ("Voice Assistant Module Test", test_voice_assistant_module),
        ("Speech Generation Test", test_speech_generation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.warning(f"⚠️ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("🏁 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The voice assistant is ready to use.")
        logger.info("\nTo run the application:")
        logger.info("  1. Make sure ELEVENLABS_API_KEY is set in your environment")
        logger.info("  2. Run: cd backend && python app.py")
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed. Please check the logs above.")
        
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
