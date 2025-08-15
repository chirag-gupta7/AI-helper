# backend/microphone_handler.py
"""
Enhanced Microphone handler for voice input using speech recognition
"""
import logging
import queue
import time
import threading
import sys

# Try to import speech recognition with improved fallback
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
    print("✅ SpeechRecognition module loaded successfully")
except ImportError as e:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None
    print(f"❌ SpeechRecognition not available: {e}")
    print("Install with: pip install SpeechRecognition")

# Try to import PyAudio
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
    print("✅ PyAudio available for microphone input")
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("❌ PyAudio not available - microphone input disabled")
    print("Install with: pip install pyaudio")

logger = logging.getLogger(__name__)

class MicrophoneHandler:
    """Enhanced microphone input and speech recognition handler"""
    
    def __init__(self, callback=None):
        self.callback = callback
        self.recognizer = None
        self.microphone = None
        self.is_listening = False
        self.listen_thread = None
        self.audio_queue = queue.Queue()
        self.initialization_successful = False
        
        # Check prerequisites
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("❌ SpeechRecognition module not available")
            return
            
        if not PYAUDIO_AVAILABLE:
            logger.error("❌ PyAudio not available - cannot access microphone")
            return
        
        # Try to initialize microphone with better error handling
        self._initialize_microphone()
    
    def _initialize_microphone(self):
        """Initialize microphone with comprehensive error handling"""
        try:
            logger.info("🎤 Initializing microphone...")
            self.recognizer = sr.Recognizer()
            
            # Try to get available microphones
            mic_list = sr.Microphone.list_microphone_names()
            if not mic_list:
                logger.error("❌ No microphones found on system")
                return
                
            logger.info(f"📱 Found {len(mic_list)} microphone(s):")
            for i, name in enumerate(mic_list[:3]):  # Show first 3
                logger.info(f"  {i}: {name}")
            
            # Initialize with default microphone
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise with timeout
            logger.info("🔧 Adjusting for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
            # Test microphone access
            logger.info("🔍 Testing microphone access...")
            with self.microphone as source:
                # Quick test to see if we can access audio
                audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=0.5)
                logger.info("✅ Microphone test successful")
                
            self.initialization_successful = True
            logger.info("✅ Microphone initialized successfully")
            
        except sr.WaitTimeoutError:
            logger.warning("⚠️ Microphone test timeout - but microphone initialized")
            self.initialization_successful = True
        except Exception as e:
            logger.error(f"❌ Failed to initialize microphone: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            self.microphone = None
            self.initialization_successful = False
    
    def start_listening(self):
        """Start listening for voice input with enhanced error handling"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("❌ SpeechRecognition not available")
            return False
            
        if not self.initialization_successful:
            logger.error("❌ Microphone not properly initialized")
            return False
            
        if self.is_listening:
            logger.warning("⚠️ Already listening")
            return True
            
        try:
            self.is_listening = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            logger.info("🎤 Started listening for voice input...")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start listening: {e}")
            self.is_listening = False
            return False
    
    def _listen_loop(self):
        """Enhanced listening loop with better error handling"""
        logger.info("🎧 Voice listening loop started")
        consecutive_errors = 0
        max_errors = 5
        
        while self.is_listening:
            try:
                with self.microphone as source:
                    logger.info("🔄 Listening for speech...")
                    # Listen with reasonable timeouts
                    audio = self.recognizer.listen(
                        source, 
                        timeout=1,           # Wait 1 second for speech to start
                        phrase_time_limit=5   # Stop listening after 5 seconds of speech
                    )
                
                logger.info("🔍 Processing speech...")
                
                # Try Google Speech Recognition first
                try:
                    text = self.recognizer.recognize_google(audio)
                    if text.strip():
                        logger.info(f"🗣️ Recognized: {text}")
                        consecutive_errors = 0  # Reset error counter
                        if self.callback:
                            self.callback(text)
                    else:
                        logger.warning("⚠️ Empty speech recognized")
                        
                except sr.UnknownValueError:
                    logger.warning("⚠️ Could not understand audio")
                except sr.RequestError as e:
                    logger.error(f"❌ Google Speech Recognition error: {e}")
                    consecutive_errors += 1
                    
            except sr.WaitTimeoutError:
                # This is normal - just means no speech detected
                continue
            except Exception as e:
                logger.error(f"❌ Listening error: {e}")
                consecutive_errors += 1
                
                if consecutive_errors >= max_errors:
                    logger.error(f"❌ Too many consecutive errors ({max_errors}), stopping listener")
                    break
                    
                time.sleep(1)  # Brief pause before retrying
        
        logger.info("🛑 Voice listening loop ended")
    
    def stop_listening(self):
        """Stop listening for voice input"""
        if self.is_listening:
            logger.info("🛑 Stopping voice listener...")
            self.is_listening = False
            if self.listen_thread:
                self.listen_thread.join(timeout=2)
            logger.info("✅ Voice listener stopped")
        else:
            logger.warning("⚠️ Voice listener was not running")
    
    def is_available(self):
        """Check if microphone functionality is available"""
        return (SPEECH_RECOGNITION_AVAILABLE and 
                PYAUDIO_AVAILABLE and 
                self.initialization_successful)
    
    def get_status(self):
        """Get current status of microphone handler"""
        return {
            'speech_recognition_available': SPEECH_RECOGNITION_AVAILABLE,
            'pyaudio_available': PYAUDIO_AVAILABLE,
            'microphone_initialized': self.initialization_successful,
            'currently_listening': self.is_listening,
            'overall_available': self.is_available()
        }
