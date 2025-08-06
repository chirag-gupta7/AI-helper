#!/usr/bin/env python3
"""
Google Calendar Authentication Refresh Script
This script will force a fresh OAuth authentication flow for Google Calendar.
"""

import os
import pickle
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Define the scope for Google Calendar access
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Get the directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')

def refresh_google_calendar_auth():
    """
    Force a fresh Google Calendar authentication flow.
    This will delete any existing token and create a new one.
    """
    print("🔄 Refreshing Google Calendar Authentication...")
    
    # Remove existing token if it exists
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
        print("✅ Removed old token file")
    
    # Check if credentials.json exists
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ Error: credentials.json not found at {CREDENTIALS_PATH}")
        print("Please ensure you have downloaded your OAuth 2.0 credentials from Google Cloud Console")
        print("and saved them as 'credentials.json' in the backend directory.")
        return False
    
    print(f"✅ Found credentials.json at {CREDENTIALS_PATH}")
    
    try:
        # Create the flow using the client secrets file
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        
        print("🌐 Starting OAuth flow...")
        print("This will open your web browser for authentication.")
        print("Please grant the requested permissions in your browser.")
        
        # Run the OAuth flow
        creds = flow.run_local_server(port=0)
        
        # Save the credentials for future use
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
        
        print(f"✅ New token saved to {TOKEN_PATH}")
        
        # Test the connection
        service = build('calendar', 'v3', credentials=creds)
        calendar = service.calendars().get(calendarId='primary').execute()
        
        print(f"✅ Successfully connected to calendar: {calendar.get('summary', 'Primary Calendar')}")
        print("🎉 Google Calendar authentication refresh completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return False

if __name__ == "__main__":
    success = refresh_google_calendar_auth()
    if success:
        print("\n✅ Authentication refresh completed successfully!")
        print("Your Google Calendar integration should now work properly.")
    else:
        print("\n❌ Authentication refresh failed!")
        print("Please check your credentials.json file and try again.")
    
    input("\nPress Enter to exit...")