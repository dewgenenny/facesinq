from db import Session
from models import ScoreHistory
from sqlalchemy import func

def inspect():
    with Session() as session:
        # distinct scores and their counts
        results = session.query(ScoreHistory.score, func.count(ScoreHistory.score)).group_by(ScoreHistory.score).all()
        print("Score Value Distribution:")
        print("Score | Count")
        print("------|------")
        for score, count in results:
            print(f"{score} | {count}")

if __name__ == "__main__":
    inspect()
