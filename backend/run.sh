#!/bin/bash

# Voice Assistant Backend Start Script for Chirag
# Usage: ./run.sh [development|production|test]

set -e  # Exit on any error

# Configuration
PROJECT_NAME="voice-assistant-backend"
PYTHON_VERSION="3.9"
VENV_NAME="venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python installation
check_python() {
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.9 or higher."
        exit 1
    fi
    
    PYTHON_VER=$(python3 --version | cut -d' ' -f2)
    print_status "Python version: $PYTHON_VER"
}

# Create virtual environment
setup_venv() {
    if [ ! -d "$VENV_NAME" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv $VENV_NAME
    else
        print_status "Virtual environment already exists."
    fi
    
    # Activate virtual environment
    source $VENV_NAME/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

# Check for required files
check_requirements() {
    print_status "Checking requirements..."
    
    # Check for required files
    required_files=("app.py" "config.py" "google_calendar_integration.py" "voice_assistant.py")
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "$file not found!"
            exit 1
        fi
    done
    
    # Check for environment file
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            print_warning ".env file not found. Please copy .env.example to .env and configure it."
            cp .env.example .env
            print_status "Created .env file from .env.example"
        else
            print_error ".env file not found and no .env.example available!"
            exit 1
        fi
    fi
    
    # Check for Google Calendar credentials
    if [ ! -f "credentials.json" ]; then
        print_warning "credentials.json not found. Please add your Google Calendar credentials."
        print_warning "You can download it from Google Cloud Console."
    fi
}

# Start the application
start_app() {
    local mode=${1:-development}
    
    print_header "🎙️  Starting Voice Assistant Backend for Chirag in $mode mode"
    print_header "==============================================================="
    
    # Set environment variables
    export FLASK_ENV=$mode
    export FLASK_APP=app.py
    
    if [ "$mode" = "development" ]; then
        export FLASK_DEBUG=true
        print_status "🚀 Starting development server..."
        print_status "📱 Access the test page at: http://localhost:5000/static/index.html"
        print_status "🔧 API documentation at: http://localhost:5000/"
        python app.py
    elif [ "$mode" = "production" ]; then
        export FLASK_DEBUG=false
        print_status "🚀 Starting production server..."
        if command_exists gunicorn; then
            gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
        else
            print_warning "Gunicorn not found. Running with Flask development server."
            python app.py
        fi
    elif [ "$mode" = "test" ]; then
        export FLASK_DEBUG=true
        export FLASK_ENV=testing
        print_status "🧪 Running tests..."
        if [ -f "test_api.py" ]; then
            python test_api.py
        else
            print_warning "test_api.py not found. Skipping tests."
        fi
        
        if [ -f "api_client.py" ]; then
            print_status "🧪 Running API client tests..."
            python api_client.py
        fi
    else
        print_error "Invalid mode: $mode. Use development, production, or test."
        exit 1
    fi
}

# Main execution
main() {
    local mode=${1:-development}
    
    print_header "🎙️  Voice Assistant Backend Setup for Chirag"
    print_header "=============================================="
    
    # Check system requirements
    check_python
    
    # Setup virtual environment
    setup_venv
    
    # Install dependencies
    install_dependencies
    
    # Check requirements
    check_requirements
    
    print_status "✅ Setup complete! Starting application..."
    
    # Start the application
    start_app $mode
}

# Handle script arguments
case "${1:-}" in
    "development"|"dev")
        main development
        ;;
    "production"|"prod")
        main production
        ;;
    "test")
        main test
        ;;
    "install")
        print_header "Installing dependencies only..."
        check_python
        setup_venv
        install_dependencies
        check_requirements
        print_status "✅ Installation complete!"
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [development|production|test|install|help]"
        echo ""
        echo "Commands:"
        echo "  development (default) - Run in development mode"
        echo "  production           - Run in production mode"
        echo "  test                 - Run tests"
        echo "  install              - Install dependencies only"
        echo "  help                 - Show this help message"
        ;;
    *)
        main development
        ;;
esac