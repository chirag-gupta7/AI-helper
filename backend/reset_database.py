#!/usr/bin/env python3
"""
Database Reset Script for Voice Assistant
This script will drop all tables and recreate them with the correct schema.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from .models import db
from .config import config
from sqlalchemy import inspect

def reset_database():
    """Reset the database by dropping and recreating all tables."""
    
    # Create Flask app
    app = Flask(__name__)
    config_name = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize database
    db.init_app(app)
    migrate = Migrate(app, db)
    
    with app.app_context():
        print("🗄️ Resetting Voice Assistant Database...")
        
        # Get database path
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        print(f"📍 Database location: {db_path}")
        
        # Drop all tables
        print("🔥 Dropping all existing tables...")
        db.drop_all()
        
        # Recreate all tables with new schema
        print("🏗️ Creating new tables with correct schema...")
        db.create_all()
        
        print("✅ Database reset complete!")
        
        # Verify tables were created
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📋 Created tables: {', '.join(tables)}")
        
        return True

if __name__ == "__main__":
    try:
        reset_database()
        print("\n🎉 SUCCESS: Database has been reset successfully!")
        print("🚀 You can now run your voice assistant application.")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to reset database: {e}")
        print("Please check your database configuration and try again.")
