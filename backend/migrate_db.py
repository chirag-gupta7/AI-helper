# backend/migrate_db.py - Corrected script to initialize the database
import os
import sys

# This is the crucial part: Add the parent directory ('AI helper') to the Python path
# This allows the script to find the 'backend' package and its modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, db

def reset_and_create_database():
    """
    Drops all tables and recreates them based on the current models.
    This ensures a clean slate and is safe for development.
    """
    with app.app_context():
        try:
            print("--- Starting Database Reset ---")
            
            # Get the database path from the app config
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            print(f"Database file located at: {db_path}")

            print("Dropping all existing tables...")
            db.drop_all()
            print("Tables dropped successfully.")

            print("Creating new tables from models...")
            db.create_all()
            print("✅ Tables created successfully!")

            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Verified tables: {', '.join(tables)}")
            print("--- Database Reset Complete ---")

        except Exception as e:
            print(f"❌ An error occurred during database reset: {e}")
            print("Please check your database configuration and model definitions.")

if __name__ == '__main__':
    reset_and_create_database()
