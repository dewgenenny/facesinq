from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///facesinq.db"  # You can change this URL to point to your database

# Creating the engine and session
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)

# Example usage