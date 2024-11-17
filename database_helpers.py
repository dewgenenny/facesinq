# database_helpers.py
from db import Session
from models import User, Score, QuizSession, decrypt_value, Workspace
from sqlalchemy.exc import SQLAlchemyError, IntegrityError




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

def add_workspace(team_id, team_name):
    """Add a workspace if it doesn't already exist in the database."""
    with Session() as session:
        existing_workspace = session.query(Workspace).filter_by(id=team_id).one_or_none()
        if not existing_workspace:
            new_workspace = Workspace(id=team_id, name=team_name)
            session.add(new_workspace)
            session.commit()

def get_all_workspaces():
    """Fetch all workspaces from the database."""
    with Session() as session:
        return session.query(Workspace).all()

def get_workspace_access_token(team_id):
    """Get the access token for a specific Slack workspace based on team_id."""
    with Session() as session:
        workspace = session.query(Workspace).filter_by(team_id=team_id).one_or_none()
        if not workspace:
            raise ValueError(f"No workspace found for team_id: {team_id}")
        return workspace.access_token


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
    """Fetch the score of a given user."""
    with Session() as session:
        try:
            score = session.query(Score).filter(Score.user_id == user_id).one_or_none()
            return score.score if score else 0
        except SQLAlchemyError as e:
            print(f"Error fetching score for User ID: {user_id}, Error: {str(e)}")
            return 0

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

def get_colleagues_excluding_user(user_id, team_id):
    """Fetch all colleagues excluding the given user from the same workspace."""
    with Session() as session:
        return session.query(User).filter(User.id != user_id, User.team_id == team_id).all()

def get_active_quiz_session(user_id):
    """Check if the user has an active quiz session."""
    with Session() as session:
        return session.query(QuizSession).filter(QuizSession.user_id == user_id).one_or_none()

def create_or_update_quiz_session(user_id, correct_user_id):
    """Create or update the quiz session for a user."""
    with Session() as session:
        try:
            quiz_session = QuizSession(user_id=user_id, correct_user_id=correct_user_id)
            session.merge(quiz_session)  # Use `merge` to replace or insert as needed
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error creating or updating quiz session for User ID: {user_id}, Error: {str(e)}")

def delete_quiz_session(user_id):
    """Delete the active quiz session for a given user."""
    with Session() as session:
        try:
            session.query(QuizSession).filter_by(user_id=user_id).delete()
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error deleting quiz session for user {user_id}: {str(e)}")

def get_top_scores(limit=10):
    """Fetch the top scoring users along with their decrypted scores."""
    with Session() as session:
        try:
            # Query the encrypted name and score columns
            top_scores = session.query(User.name_encrypted, Score.score).join(Score).order_by(Score.score.desc()).limit(limit).all()

            # Decrypt the names after retrieving from the database
            decrypted_scores = []
            for name_encrypted, score in top_scores:
                try:
                    name_decrypted = decrypt_value(name_encrypted)
                    decrypted_scores.append((name_decrypted, score))
                except Exception as e:
                    print(f"Error decrypting name: {str(e)}")
                    decrypted_scores.append(("Unknown", score))  # Handle decryption errors gracefully

            return decrypted_scores

        except SQLAlchemyError as e:
            print(f"Error fetching top scores: {str(e)}")
            return []


def add_or_update_user(user_id, name, image, team_id):
    """Add a new user or update an existing one in the database for a specific team."""
    with Session() as session:
        try:
            existing_user = session.query(User).filter_by(id=user_id).one_or_none()
            if existing_user:
                # Update the existing user using the provided team_id
                existing_user.name = name
                existing_user.image = image
                existing_user.team_id = team_id  # Make sure the team_id is updated if needed
            else:
                # Add a new user with the correct team_id
                new_user = User(id=user_id, team_id=team_id, opted_in=False)
                new_user.name = name
                new_user.image = image
                session.add(new_user)

            session.commit()
        except IntegrityError as e:
            session.rollback()
            print(f"Failed to insert/update user {user_id}: {str(e)}")
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error while adding/updating user {user_id}: {str(e)}")


def does_user_exist(team_id):
    """Check if users already exist in the database for a specific team."""
    with Session() as session:
        return session.query(User).filter_by(team_id=team_id).count() > 0