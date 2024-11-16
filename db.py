# db.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///facesinq.db"

engine = create_engine(DATABASE_URL)
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
