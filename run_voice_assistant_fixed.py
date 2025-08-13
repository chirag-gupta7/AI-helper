"""
Fixed startup script for the Voice Assistant Backend
This script applies all necessary patches and runs the application safely.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def install_requirements():
    """Install the fixed requirements"""
    requirements_file = Path(__file__).parent / "backend" / "requirements_fixed.txt"
    
    if not requirements_file.exists():
        logger.error(f"Requirements file not found: {requirements_file}")
        return False
    
    try:
        logger.info("Installing compatible requirements...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install requirements: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return False

def main():
    """Main function to run the fixed voice assistant"""
    try:
        # Change to the project directory
        project_root = Path(__file__).parent
        os.chdir(project_root)
        
        # Verify environment variables are loaded
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        if api_key:
            logger.info("✅ ElevenLabs API key loaded successfully")
        else:
            logger.warning("⚠️ ElevenLabs API key not found in environment variables")
            logger.warning("⚠️ Make sure your .env file is in the root directory and contains ELEVENLABS_API_KEY")
        
        # Install requirements
        if not install_requirements():
            logger.error("Failed to install requirements. Exiting.")
            return 1
        
        # Run the fixed version
        logger.info("Starting Voice Assistant with compatibility fixes...")
        
        # Use the fixed runner
        result = subprocess.run(
            [sys.executable, "-m", "backend.run_without_gevent_fixed"],
            cwd=project_root
        )
        
        return result.returncode
        
    except KeyboardInterrupt:
        logger.info("Voice Assistant stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error running Voice Assistant: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())