from db import engine, Session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_columns():
    with engine.connect() as connection:
        try:
            # Add last_quiz_sent_at
            logger.info("Adding last_quiz_sent_at column...")
            connection.execute(text("ALTER TABLE users ADD COLUMN last_quiz_sent_at DATETIME"))
            logger.info("Added last_quiz_sent_at column.")
        except Exception as e:
            logger.warning(f"Could not add last_quiz_sent_at (might already exist): {e}")

        try:
            # Add next_random_quiz_at
            logger.info("Adding next_random_quiz_at column...")
            connection.execute(text("ALTER TABLE users ADD COLUMN next_random_quiz_at DATETIME"))
            logger.info("Added next_random_quiz_at column.")
        except Exception as e:
            logger.warning(f"Could not add next_random_quiz_at (might already exist): {e}")

        try:
            # Add total_attempts
            logger.info("Adding total_attempts column...")
            connection.execute(text("ALTER TABLE scores ADD COLUMN total_attempts INTEGER DEFAULT 0"))
            logger.info("Added total_attempts column.")
        except Exception as e:
            logger.warning(f"Could not add total_attempts (might already exist): {e}")

if __name__ == "__main__":
    add_columns()
