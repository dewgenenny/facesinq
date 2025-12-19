from db import Session
from models import Score, ScoreHistory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_scores():
    """Multiply all existing scores by 10."""
    with Session() as session:
        try:
            # Update Score table
            scores = session.query(Score).all()
            for score in scores:
                score.score *= 10
            
            # Update ScoreHistory table
            history_entries = session.query(ScoreHistory).all()
            for entry in history_entries:
                entry.score *= 10
                
            session.commit()
            logger.info(f"Successfully migrated {len(scores)} scores and {len(history_entries)} history entries.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error migrating scores: {e}")

if __name__ == "__main__":
    migrate_scores()
