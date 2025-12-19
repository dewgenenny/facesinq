from db import engine, Session
from sqlalchemy import text
from models import Score, ScoreHistory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    # 1. Add columns if they don't exist
    with engine.connect() as connection:
        try:
            logger.info("Adding correct_attempts to scores...")
            connection.execute(text("ALTER TABLE scores ADD COLUMN correct_attempts INTEGER DEFAULT 0"))
        except Exception as e:
            logger.warning(f"Could not add correct_attempts (might exist): {e}")

        try:
            logger.info("Adding is_correct to score_history...")
            connection.execute(text("ALTER TABLE score_history ADD COLUMN is_correct BOOLEAN DEFAULT 0"))
        except Exception as e:
            logger.warning(f"Could not add is_correct (might exist): {e}")

    # 2. Backfill Data
    logger.info("Backfilling data...")
    with Session() as session:
        # Update ScoreHistory: if score >= 10, is_correct = True
        logger.info("Updating ScoreHistory is_correct...")
        history_rows = session.query(ScoreHistory).all()
        for h in history_rows:
            # Heuristic: Correct answers gave 10+ points usually. Incorrect gave < 10.
            # Base points for correct is 10. Streak adds 5.
            # Incorrect is 2.
            if h.score >= 10:
                h.is_correct = True
            else:
                h.is_correct = False
        session.commit()

        # Recalculate Score.correct_attempts
        logger.info("Recalculating Score.correct_attempts...")
        scores = session.query(Score).all()
        for s in scores:
            correct_count = session.query(ScoreHistory).filter(
                ScoreHistory.user_id == s.user_id,
                ScoreHistory.is_correct == True
            ).count()
            s.correct_attempts = correct_count
            logger.info(f"User {s.user_id}: correct_attempts set to {correct_count}")
        
        session.commit()
    logger.info("Migration complete.")

if __name__ == "__main__":
    migrate()
