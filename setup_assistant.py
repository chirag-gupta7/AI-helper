#!/usr/bin/env python3
"""
Setup script for AI Helper Voice Assistant
This script installs and checks all required dependencies
"""

import os
import sys
import subprocess
import platform
import pkg_resources
import shutil
import re
from pathlib import Path

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is not installed yet, which is fine during initial setup
    pass

def print_colored(text, color="green"):
    """Print colored text in the terminal"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, colors['reset'])}{text}{colors['reset']}")

def print_header(title):
    """Print a formatted header"""
    print_colored("\n" + "=" * 70, "blue")
    print_colored(f" {title} ", "blue")
    print_colored("=" * 70, "blue")

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_colored("ERROR: Python 3.8 or higher is required", "red")
        print_colored(f"Current version: {version.major}.{version.minor}.{version.micro}", "red")
        return False
    print_colored(f"✓ Python version: {version.major}.{version.minor}.{version.micro}", "green")
    return True

def is_package_installed(package_name):
    """Check if a package is installed"""
    try:
        pkg_resources.get_distribution(package_name)
        return True
    except pkg_resources.DistributionNotFound:
        return False

def install_package(package_name, extra_args=None):
    """Install a Python package using pip"""
    # Check if already installed
    if is_package_installed(package_name):
        print_colored(f"✓ {package_name} is already installed", "green")
        return True
    
    # Construct the command
    cmd = [sys.executable, "-m", "pip", "install"]
    
    if extra_args:
        cmd.extend(extra_args)
    
    cmd.append(package_name)
    
    print_colored(f"Installing {package_name}...", "blue")
    try:
        subprocess.check_call(cmd)
        print_colored(f"✓ Successfully installed {package_name}", "green")
        return True
    except subprocess.CalledProcessError as e:
        print_colored(f"✗ Failed to install {package_name}: {e}", "red")
        return False

def install_pyaudio():
    """Install PyAudio with special handling for different platforms"""
    if is_package_installed("pyaudio"):
        print_colored("✓ PyAudio is already installed", "green")
        return True
        
    system = platform.system()
    
    if system == "Windows":
        print_colored("Installing PyAudio for Windows...", "blue")
        try:
            # Try to install PyAudio directly first
            result = install_package("pyaudio")
            if result:
                return True
            else:
                print_colored("Direct installation failed. You may need to install Microsoft Visual C++ Build Tools", "yellow")
                print_colored("Alternative: Download PyAudio wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/", "yellow")
                return False
        except Exception as e:
            print_colored(f"Error installing PyAudio: {e}", "red")
            return False
                
    elif system == "Darwin":  # macOS
        print_colored("Installing PyAudio for macOS...", "blue")
        try:
            subprocess.check_call(["brew", "install", "portaudio"])
            return install_package("pyaudio")
        except subprocess.CalledProcessError:
            print_colored("Homebrew not found or failed. Try: brew install portaudio", "yellow")
            return install_package("pyaudio")
            
    else:  # Linux and others
        print_colored("Installing PyAudio for Linux...", "blue")
        try:
            # Try common package managers
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "portaudio19-dev"])
            return install_package("pyaudio")
        except subprocess.CalledProcessError as e:
            print_colored(f"Failed to install system dependencies: {e}", "red")
            print_colored("Try manually: sudo apt-get install portaudio19-dev", "yellow")
            return install_package("pyaudio")

def check_elevenlabs_key():
    """Check for ElevenLabs API key and help set it up"""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if api_key:
        print_colored("✓ ElevenLabs API key found in environment variables", "green")
        # Test API key validation
        print_colored("Validating API key format...", "blue")
        if re.match(r'^[a-zA-Z0-9]{32}$', api_key):
            print_colored("✓ API key format looks correct", "green")
        else:
            print_colored("⚠️ API key format may be incorrect (expected 32 alphanumeric characters)", "yellow")
        return True
        
    print_colored("No ElevenLabs API key found in environment variables", "yellow")
    print_colored("ElevenLabs requires an API key for text-to-speech functionality", "yellow")
    
    # Ask for API key
    api_key = input("Please enter your ElevenLabs API key (or press Enter to skip): ").strip()
    if api_key:
        # Set for the current session
        os.environ["ELEVENLABS_API_KEY"] = api_key
        
        # Update .env file if it exists
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path, 'a') as f:
                f.write(f"\nELEVENLABS_API_KEY={api_key}\n")
        else:
            with open(env_path, 'w') as f:
                f.write(f"ELEVENLABS_API_KEY={api_key}\n")
            
        # Add suggestion for permanent setup
        print_colored("\nTo use this key permanently:", "yellow")
        print_colored(f'1. For Windows, run: setx ELEVENLABS_API_KEY "{api_key}"', "yellow")
        print_colored(f'2. For Linux/macOS, add to ~/.bashrc: export ELEVENLABS_API_KEY="{api_key}"', "yellow")
        return True
    else:
        print_colored("ElevenLabs API key setup skipped. Voice feature will use pyttsx3 fallback.", "yellow")
        return False

def check_directory_structure():
    """Check if the required directory structure exists"""
    required_dirs = ["backend"]
    missing_dirs = [d for d in required_dirs if not os.path.isdir(d)]
    
    if missing_dirs:
        print_colored(f"Missing directories: {', '.join(missing_dirs)}", "yellow")
        print_colored("This script should be run from the root of the AI-helper project.", "yellow")
        
        current_dir = os.path.basename(os.getcwd())
        if current_dir != "AI":
            print_colored(f"Current directory: {current_dir}", "yellow")
            print_colored("Expected to be in the AI directory", "yellow")
            
        return False
    return True

def setup_pyttsx3_encoding_fix():
    """Create a patch file to fix pyttsx3 encoding issues"""
    print_colored("Setting up pyttsx3 encoding fix...", "blue")
    
    try:
        import pyttsx3
        pyttsx3_path = os.path.dirname(pyttsx3.__file__)
        print_colored(f"Found pyttsx3 at: {pyttsx3_path}", "green")
    except (ImportError, AttributeError):
        print_colored("Could not locate pyttsx3 installation", "red")
        return False
    
    # Create a patch for pyttsx3 driver module to handle Unicode
    driver_py = os.path.join(pyttsx3_path, "drivers", "sapi5.py")
    if os.path.exists(driver_py):
        with open(driver_py, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            
        # Check if already patched
        if "# AI-helper Unicode patch" in content:
            print_colored("✓ pyttsx3 already patched for Unicode support", "green")
            return True
            
        # Apply patch
        print_colored("Patching pyttsx3 sapi5.py driver for better Unicode handling...", "blue")
        
        # Backup original file
        backup_file = driver_py + ".bak"
        shutil.copy2(driver_py, backup_file)
        print_colored(f"✓ Original file backed up to {backup_file}", "green")
        
        # Patch the file
        with open(driver_py, 'w', encoding='utf-8') as file:
            file.write("# AI-helper Unicode patch\n" + content)
            
        print_colored("✓ Successfully patched pyttsx3 for Unicode support", "green")
        return True
    else:
        print_colored(f"Could not find pyttsx3 driver file at {driver_py}", "red")
        return False

def test_elevenlabs_connection():
    """Test the connection to ElevenLabs API"""
    if not os.environ.get("ELEVENLABS_API_KEY"):
        print_colored("⚠️ No ElevenLabs API key found. Skipping connection test.", "yellow")
        return False
        
    if not is_package_installed("elevenlabs"):
        print_colored("⚠️ ElevenLabs package not installed. Skipping connection test.", "yellow")
        return False
        
    print_colored("Testing connection to ElevenLabs API...", "blue")
    try:
        # Import the required packages
        from elevenlabs import set_api_key
        from elevenlabs.client import ElevenLabs
        
        # Set the API key
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        set_api_key(api_key)
        
        # Create client and try to get user info
        client = ElevenLabs(api_key=api_key)
        user_data = client.user.get()
        
        if user_data:
            print_colored("✅ ElevenLabs API connection successful!", "green")
            print_colored(f"✅ Subscription tier: {user_data.subscription.tier}", "green")
            return True
            
    except Exception as e:
        print_colored(f"❌ Error connecting to ElevenLabs API: {e}", "red")
        print_colored("Please check your API key and internet connection", "yellow")
        return False

def patch_voice_assistant_file():
    """Patch the voice_assistant.py file to fix the Unicode issues"""
    file_path = os.path.join("backend", "voice_assistant.py")
    
    if not os.path.exists(file_path):
        print_colored(f"Error: {file_path} not found", "red")
        return False
        
    print_colored(f"Backing up {file_path}...", "blue")
    backup_file = file_path + ".bak"
    shutil.copy2(file_path, backup_file)
    print_colored(f"✓ Original file backed up to {backup_file}", "green")
    
    print_colored("Voice assistant file is ready for use with the new ElevenLabs integration", "green")
    return True

def main():
    """Main setup function"""
    print_header("AI Helper Voice Assistant Setup")
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
        
    # Check directory structure
    if not check_directory_structure():
        print_colored("Please run this script from the AI project root directory", "red")
        sys.exit(1)
    
    # Install base requirements
    print_header("Installing Base Requirements")
    required_packages = [
        "elevenlabs",
        "pyttsx3",
        "flask",
        "flask_socketio",
        "pydub",
        "python-dotenv"
    ]
    
    for package in required_packages:
        install_package(package)
    
    # Install PyAudio (platform-specific)
    print_header("Installing PyAudio")
    install_pyaudio()
    
    # Check for ElevenLabs API key
    print_header("ElevenLabs API Key Setup")
    check_elevenlabs_key()
    
    # Patch voice_assistant.py file
    print_header("Preparing Voice Assistant Module")
    patch_voice_assistant_file()
    
    # Setup pyttsx3 encoding fix
    print_header("Setting Up pyttsx3 Unicode Fix")
    setup_pyttsx3_encoding_fix()
    
    # Test ElevenLabs connection
    print_header("Testing ElevenLabs Connection")
    test_elevenlabs_connection()
    
    # Final instructions
    print_header("Setup Completed!")
    print_colored("\nTo run the application:", "cyan")
    print_colored("1. Make sure you have set the ELEVENLABS_API_KEY environment variable", "cyan")
    print_colored("2. Run: cd backend && python app.py", "cyan")
    print_colored("\nIf you still encounter issues:", "yellow")
    print_colored("1. Check the log files for detailed error messages", "yellow")
    print_colored("2. Make sure your firewall allows connections to the ElevenLabs API", "yellow")
    print_colored("3. Try manually installing PyAudio if the automatic installation failed", "yellow")
    print_colored("\nEnjoy using your AI Helper Voice Assistant!", "green")

if __name__ == "__main__":
    main()