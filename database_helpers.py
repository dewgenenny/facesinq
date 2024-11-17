# database_helpers.py
from db import Session
from models import User, Score, QuizSession
from sqlalchemy.exc import SQLAlchemyError




# TODO - Use this to simplify below functions further....
# def execute_in_session(func, *args, **kwargs):
#     """Utility function that wraps session handling for a given function."""
#     with Session() as session:
#         try:
#             result = func(session, *args, **kwargs)
#             session.commit()
#             return result
#         except SQLAlchemyError as e:
#             session.rollback()
#             print(f"Database error: {str(e)}")
#             raise  # Re-raise the exception so the caller can handle it if needed

def get_user_name(user_id):
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).one_or_none()
        return user.name if user else "Unknown"

def has_user_opted_in(user_id):
    session = Session()  # Create a new session
    try:
        user = session.query(User).filter_by(id=user_id).one_or_none()  # Query using the session
        print(f"Getting user opt-in for User ID: {user_id}")
        if user:
            return user.opted_in is True
        return False
    except Exception as e:
        print(f"Error fetching user opt-in for User ID: {user_id}, Error: {str(e)}")
        return False
    finally:
        session.close()  # Close the session

def get_user_score(user_id):
    session = Session()
    try:
        # Fetch the user score
        score = session.query(Score).filter(Score.user_id == user_id).one_or_none()
        return score.score if score else 0
    except Exception as e:
        print(f"Error fetching score for User ID: {user_id}, Error: {str(e)}")
        return 0
    finally:
        session.close()

def get_opted_in_user_count():
    session = Session()
    try:
        count = session.query(User).filter(User.opted_in == True).count()
        return count
    except Exception as e:
        print(f"Error fetching opted-in user count: {str(e)}")
        return 0
    finally:
        session.close()


def get_user(user_id):
    with Session() as session:
        return session.query(User).filter_by(id=user_id).one_or_none()

def update_score(user_id, points):
    with Session() as session:
        score = session.query(Score).filter(Score.user_id == user_id).one_or_none()
        if score:
            score.score += points
        else:
            score = Score(user_id=user_id, score=points)
            session.add(score)
        session.commit()

def update_user_opt_in(user_id, opt_in):
    """Updates the opt-in status for a user."""
    with Session() as session:
        try:
            user = session.query(User).filter_by(id=user_id).one_or_none()
            if user:
                user.opted_in = opt_in
                session.commit()
                print(f"User {user_id} opt-in updated to {opt_in}")
            else:
                print(f"No user found with User ID: {user_id}")
        except SQLAlchemyError as e:
            print(f"Error updating user opt-in for User ID: {user_id}, Error: {str(e)}")
            session.rollback()  # Rollback the transaction in case of an error