from db import Session
from models import Score
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_data():
    session = Session()
    try:
        # Find scores where total_attempts < score
        inconsistent_scores = session.query(Score).filter(Score.total_attempts < Score.score).all()
        
        logger.info(f"Found {len(inconsistent_scores)} inconsistent scores.")
        
        for score in inconsistent_scores:
            logger.info(f"Fixing user {score.user_id}: Score={score.score}, Attempts={score.total_attempts} -> Attempts={score.score}")
            score.total_attempts = score.score
            
        session.commit()
        logger.info("Data fix completed successfully.")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error fixing data: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_data()
