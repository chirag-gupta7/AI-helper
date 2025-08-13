#!/usr/bin/env python3
"""
ElevenLabs API Key Verification Script
This script checks if your ELEVENLABS_API_KEY is properly configured throughout the codebase
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

def print_colored(text, color="green"):
    """Print colored text"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m", 
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, colors['reset'])}{text}{colors['reset']}")

def check_env_file():
    """Check if .env file exists and contains the API key"""
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path("backend/.env")
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            if "ELEVENLABS_API_KEY=" in content:
                print_colored("✅ ELEVENLABS_API_KEY found in .env file", "green")
                return True
            else:
                print_colored("❌ ELEVENLABS_API_KEY not found in .env file", "red")
                return False
    else:
        print_colored("❌ .env file not found", "red")
        return False

def check_environment_variable():
    """Check if the environment variable is loaded"""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if api_key:
        print_colored(f"✅ Environment variable loaded (length: {len(api_key)})", "green")
        return True
    else:
        print_colored("❌ Environment variable not loaded", "red")
        return False

def test_modules():
    """Test if modules can access the API key"""
    results = []
    
    # Test config module
    try:
        sys.path.insert(0, str(Path("backend")))
        from backend.config import Config
        if hasattr(Config, 'API_KEY') and Config.API_KEY:
            print_colored("✅ Config module has API key", "green")
            results.append(True)
        else:
            print_colored("❌ Config module missing API key", "red")
            results.append(False)
    except Exception as e:
        print_colored(f"❌ Config module error: {e}", "red")
        results.append(False)
    
    # Test ElevenLabs integration
    try:
        from backend.elevenlabs_integration import ElevenLabsService
        service = ElevenLabsService()
        if service.api_key:
            print_colored("✅ ElevenLabs integration has API key", "green")
            results.append(True)
        else:
            print_colored("❌ ElevenLabs integration missing API key", "red")
            results.append(False)
    except Exception as e:
        print_colored(f"❌ ElevenLabs integration error: {e}", "red")
        results.append(False)
        
    # Test voice assistant
    try:
        from backend.voice_assistant import API_KEY
        if API_KEY:
            print_colored("✅ Voice assistant has API key", "green")
            results.append(True)
        else:
            print_colored("❌ Voice assistant missing API key", "red")
            results.append(False)
    except Exception as e:
        print_colored(f"❌ Voice assistant error: {e}", "red")
        results.append(False)
    
    return all(results)

def main():
    """Main verification function"""
    print_colored("🔍 ElevenLabs API Key Configuration Verification", "cyan")
    print_colored("=" * 60, "cyan")
    
    checks = [
        ("Environment File", check_env_file),
        ("Environment Variable", check_environment_variable),
        ("Module Integration", test_modules)
    ]
    
    all_passed = True
    for name, check_func in checks:
        print_colored(f"\n📋 Checking {name}...", "blue")
        result = check_func()
        if not result:
            all_passed = False
    
    print_colored("\n" + "=" * 60, "cyan")
    if all_passed:
        print_colored("🎉 All ElevenLabs API configuration checks passed!", "green")
        print_colored("Your ELEVENLABS_API_KEY is properly configured throughout the codebase.", "green")
    else:
        print_colored("⚠️  Some configuration issues were found.", "yellow")
        print_colored("Please check the issues above and ensure your .env file is properly configured.", "yellow")

if __name__ == "__main__":
    main()
