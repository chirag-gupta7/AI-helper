#!/bin/bash

echo "🔧 Fixing Voice Assistant Backend..."

# Fix directory structure
echo "Creating static directory..."
mkdir -p static

# Move index.html if it's in wrong location
if [ -f "index.html" ]; then
    mv index.html static/
    echo "✅ Moved index.html to static folder"
fi

# Fix voice_assistant.py import
echo "Fixing voice_assistant.py import..."
sed -i 's/from backend.google_calendar_integration import/from google_calendar_integration import/g' voice_assistant.py
echo "✅ Fixed import in voice_assistant.py"

# Make run script executable
chmod +x run.sh

# Check if all required files exist
echo "📁 Checking file structure..."
for file in "app.py" "config.py" "google_calendar_integration.py" "voice_assistant.py" ".env" "credentials.json"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done

if [ -f "static/index.html" ]; then
    echo "✅ static/index.html exists"
else
    echo "❌ static/index.html missing"
fi

echo ""
echo "🚀 Starting the server..."
echo "📱 Test page will be available at: http://localhost:5000/static/index.html"
echo "🔧 API root will be at: http://localhost:5000/"
echo ""

# Start the server
./run.sh development