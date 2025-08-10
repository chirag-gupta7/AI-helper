# backend/microphone_handler.py
"""
Microphone handler for voice input using speech recognition
"""
import logging
import queue
import time
import threading

# Try to import speech recognition with fallback
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError as e:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None
    print(f"SpeechRecognition not available: {e}")

logger = logging.getLogger(__name__)

class MicrophoneHandler:
    """Handle microphone input and speech recognition"""
    
    def __init__(self, callback=None):
        self.callback = callback
        self.recognizer = None
        self.microphone = None
        self.is_listening = False
        self.listen_thread = None
        self.audio_queue = queue.Queue()
        
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("❌ SpeechRecognition module not available")
            return
        
        # Try to initialize microphone
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
            logger.info("✅ Microphone initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize microphone: {e}")
            self.microphone = None
    
    def start_listening(self):
        """Start listening for voice input"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("❌ SpeechRecognition not available")
            return False
            
        if not self.microphone:
            logger.error("❌ No microphone available")
            return False
            
        if self.is_listening:
            logger.warning("⚠️  Already listening")
            return False
        
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        logger.info("🎤 Started listening for voice input")
        return True
    
    def stop_listening(self):
        """Stop listening for voice input"""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=2)
        logger.info("🛑 Stopped listening for voice input")
    
    def _listen_loop(self):
        """Main listening loop"""
        while self.is_listening:
            try:
                with self.microphone as source:
                    logger.info("👂 Listening...")
                    # Listen for audio with timeout
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)
                
                # Process audio in background
                threading.Thread(
                    target=self._process_audio, 
                    args=(audio,), 
                    daemon=True
                ).start()
                
            except sr.WaitTimeoutError:
                # Normal timeout, continue listening
                pass
            except Exception as e:
                logger.error(f"❌ Error in listen loop: {e}")
                time.sleep(1)
    
    def _process_audio(self, audio):
        """Process audio and convert to text"""
        try:
            # Try Google Speech Recognition
            text = self.recognizer.recognize_google(audio)
            logger.info(f"🎯 Recognized: {text}")
            
            if self.callback:
                self.callback(text)
                
        except sr.UnknownValueError:
            logger.debug("🤷 Could not understand audio")
        except sr.RequestError as e:
            logger.error(f"❌ Speech recognition error: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing audio: {e}")
