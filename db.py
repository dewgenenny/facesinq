# db.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use DATABASE_URL from environment if available
# Read the DATABASE_URL from the environment and replace `postgres://` if needed
raw_database_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/facesinq.db')
if raw_database_url.startswith("postgres://"):
    raw_database_url = raw_database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(raw_database_url)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Function to initialize the database
def initialize_database():
    print("Initializing the database...")
    Base.metadata.create_all(bind=engine)  # Create all tables if they do not exist
    print("Database initialized successfully.")

# Run this function if you want to manually create tables
if __name__ == "__main__":
    initialize_database()
