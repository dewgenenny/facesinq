# database_helpers.py
from db import Session
from models import User, Score, QuizSession, decrypt_value, Workspace, ScoreHistory
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound




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

def add_workspace(team_id, team_name, access_token):
    """Add a new workspace to the database or update an existing one."""
    with Session() as session:
        try:
            workspace = session.query(Workspace).filter_by(id=team_id).one_or_none()
            if workspace:
                # Update the existing workspace
                workspace.name = team_name
                workspace.access_token = access_token  # Automatically encrypts the token
            else:
                # Add a new workspace with encrypted access token
                new_workspace = Workspace(id=team_id, name=team_name)
                new_workspace.access_token = access_token  # Automatically encrypts the token
                session.add(new_workspace)

            session.commit()
        except IntegrityError as e:
            session.rollback()
            print(f"Failed to add/update workspace {team_id}: {str(e)}")
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error while adding/updating workspace {team_id}: {str(e)}")

def get_all_workspaces():
    """Fetch all workspaces from the database."""
    with Session() as session:
        return session.query(Workspace).all()

def get_workspace_access_token(team_id):
    """Get the access token for a specific Slack workspace based on workspace ID."""
    with Session() as session:
        try:
            workspace = session.query(Workspace).filter_by(id=team_id).one_or_none()
            if not workspace:
                raise ValueError(f"No workspace found for team_id: {team_id}")
            return workspace.access_token  # Automatically decrypts the token
        except Exception as e:
            print(f"[ERROR] Failed to retrieve workspace for team_id {team_id}: {str(e)}")
            raise e

def get_user_access_token(user_id):
    """Retrieve the access token for the workspace associated with the user_id."""
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).one_or_none()
        if not user:
            raise ValueError(f"No user found with user_id: {user_id}")

        # Get the workspace from the user information
        workspace = session.query(Workspace).filter_by(id=user.team_id).one_or_none()
        if not workspace:
            raise ValueError(f"No workspace found for team_id associated with user_id: {user_id}")

        return workspace.access_token

def does_workspace_exist(team_id):
    """Check if a workspace with the given team_id exists in the database."""
    with Session() as session:
        return session.query(Workspace).filter_by(id=team_id).one_or_none() is not None


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

def get_user_attempts(user_id):
    """Fetch the total attempts of a given user."""
    with Session() as session:
        try:
            score = session.query(Score).filter(Score.user_id == user_id).one_or_none()
            return score.total_attempts if score else 0
        except SQLAlchemyError as e:
            print(f"Error fetching attempts for User ID: {user_id}, Error: {str(e)}")
            return 0

def get_random_user_images(limit=3):
    """Fetch a list of random user image URLs."""
    from sqlalchemy.sql.expression import func
    with Session() as session:
        try:
            # Query users with images, order by random
            users = session.query(User.image_encrypted).filter(User.image_encrypted != None).order_by(func.random()).limit(limit).all()
            
            images = []
            for (image_encrypted,) in users:
                try:
                    image_decrypted = decrypt_value(image_encrypted)
                    if image_decrypted:
                        images.append(image_decrypted)
                except Exception:
                    continue
            return images
        except SQLAlchemyError as e:
            print(f"Error fetching random user images: {str(e)}")
            return []

def get_global_stats():
    """Fetch global statistics for the game."""
    from sqlalchemy import func
    with Session() as session:
        try:
            # Total players (users with at least one attempt)
            total_players = session.query(Score).filter(Score.total_attempts > 0).count()
            
            # Total questions answered
            total_questions = session.query(func.sum(Score.total_attempts)).scalar() or 0
            
            # Total correct answers (score represents correct answers)
            total_correct = session.query(func.sum(Score.score)).scalar() or 0
            
            # Average accuracy
            accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0.0
            
            return {
                'players': total_players,
                'questions': total_questions,
                'accuracy': accuracy
            }
        except SQLAlchemyError as e:
            print(f"Error fetching global stats: {str(e)}")
            return {'players': 0, 'questions': 0, 'accuracy': 0.0}

def get_opted_in_user_count(team_id):
    """Get the count of users who have opted in for a specific team."""
    session = Session()
    try:
        # Filter users by team_id and opted_in == True
        count = session.query(User).filter(User.team_id == team_id, User.opted_in == True).count()
        return count
    except Exception as e:
        print(f"Error fetching opted-in user count for team_id {team_id}: {str(e)}")
        return 0
    finally:
        session.close()

def get_user(user_id):
    with Session() as session:
        return session.query(User).filter_by(id=user_id).one_or_none()

def update_score(user_id, points):
    from datetime import datetime
    with Session() as session:
        score = session.query(Score).filter(Score.user_id == user_id).one_or_none()
        if score:
            score.score += points
            score.total_attempts += 1
        else:
            score = Score(user_id=user_id, score=points, total_attempts=1)
            session.add(score)
        
        # Add history record
        history = ScoreHistory(user_id=user_id, score=points, created_at=datetime.utcnow())
        session.add(history)
        
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
                return True
            else:
                print(f"No user found with User ID: {user_id}")
                return False

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

def reset_quiz_session(user_id):
    """Resets the quiz session for the given user, if one exists."""
    with Session() as session:
        try:
            # Find the active quiz session for the user
            quiz_session = session.query(QuizSession).filter_by(user_id=user_id).one_or_none()

            if quiz_session:
                session.delete(quiz_session)
                session.commit()
                print(f"Quiz session for user {user_id} has been successfully reset.")
            else:
                print(f"No active quiz session found for user {user_id} to reset.")

        except NoResultFound:
            print(f"No active quiz session found for user {user_id}.")
        except Exception as e:
            session.rollback()
            print(f"An error occurred while resetting quiz session for user {user_id}: {str(e)}")


def get_top_scores(limit=10):
    """Fetch the top scoring users along with their decrypted scores."""
    with Session() as session:
        try:
            # Query the encrypted name, encrypted image, score, total_attempts, and current_streak columns
            # We fetch all scores first to calculate percentage and filter in Python (easier for percentage calculation)
            # Or we can do it in SQL if we want to be more efficient, but Python is fine for small datasets
            all_scores = session.query(User.name_encrypted, User.image_encrypted, Score.score, Score.total_attempts, User.current_streak).join(Score).all()

            # Process scores: decrypt, calculate percentage, filter
            processed_scores = []
            for name_encrypted, image_encrypted, score, total_attempts, current_streak in all_scores:
                if total_attempts < 10:
                    continue
                
                try:
                    name_decrypted = decrypt_value(name_encrypted)
                    image_decrypted = decrypt_value(image_encrypted)
                    percentage = (score / total_attempts) * 100
                    processed_scores.append({
                        'name': name_decrypted,
                        'score': score,
                        'total_attempts': total_attempts,
                        'percentage': percentage,
                        'image_url': image_decrypted,
                        'current_streak': current_streak
                    })
                except Exception as e:
                    print(f"Error processing score for user: {str(e)}")
                    continue

            # Sort by percentage descending
            processed_scores.sort(key=lambda x: x['percentage'], reverse=True)

            # Return top 'limit' scores
            # Returning tuple compatible with leaderboard.py expectations (name, percentage, image_url, score, total_attempts, current_streak)
            return [(s['name'], s['percentage'], s['image_url'], s['score'], s['total_attempts'], s['current_streak']) for s in processed_scores[:limit]]

        except SQLAlchemyError as e:
            print(f"Error fetching top scores: {str(e)}")
            return []

def get_top_scores_period(start_date, limit=5):
    """Fetch top scores since a specific date."""
    from sqlalchemy import func
    with Session() as session:
        try:
            # Aggregate scores from history
            # We need to join with User to get names/images
            results = session.query(
                ScoreHistory.user_id,
                func.sum(ScoreHistory.score).label('total_score'),
                func.count(ScoreHistory.id).label('total_attempts'),
                User.name_encrypted,
                User.image_encrypted,
                User.current_streak
            ).join(User)\
            .filter(ScoreHistory.created_at >= start_date)\
            .group_by(ScoreHistory.user_id, User.name_encrypted, User.image_encrypted, User.current_streak)\
            .all()

            processed_scores = []
            for user_id, score, total_attempts, name_encrypted, image_encrypted, current_streak in results:
                if total_attempts < 1: # Show anyone who has played at least once in the period
                    continue
                
                try:
                    name_decrypted = decrypt_value(name_encrypted)
                    image_decrypted = decrypt_value(image_encrypted)
                    percentage = (score / total_attempts) * 100
                    processed_scores.append({
                        'name': name_decrypted,
                        'score': score,
                        'total_attempts': total_attempts,
                        'percentage': percentage,
                        'image_url': image_decrypted,
                        'current_streak': current_streak
                    })
                except Exception as e:
                    continue

            # Sort by percentage descending, then total score descending
            processed_scores.sort(key=lambda x: (x['percentage'], x['score']), reverse=True)

            return [(s['name'], s['percentage'], s['image_url'], s['score'], s['total_attempts'], s['current_streak']) for s in processed_scores[:limit]]

        except SQLAlchemyError as e:
            print(f"Error fetching period scores: {str(e)}")
            return []


def add_or_update_user(user_id, name, image, team_id):
    """Add a new user or update an existing one in the database for a specific team."""
    with Session() as session:
        try:
            existing_user = session.query(User).filter_by(id=user_id, team_id=team_id).one_or_none()  # Updated to filter by team_id
            if existing_user:
                # Update the existing user using the provided team_id
                existing_user.name = name
                existing_user.image = image
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

def get_users_due_for_quiz():
    """Fetch users who are opted in and due for a random quiz."""
    from datetime import datetime
    with Session() as session:
        now = datetime.utcnow()
        # Users opted in AND (next_random_quiz_at is NULL OR next_random_quiz_at <= now)
        return session.query(User).filter(
            User.opted_in == True,
            (User.next_random_quiz_at == None) | (User.next_random_quiz_at <= now)
        ).all()

def update_user_quiz_schedule(user_id, next_quiz_at):
    """Update the next scheduled quiz time for a user."""
    from datetime import datetime
    with Session() as session:
        try:
            user = session.query(User).filter_by(id=user_id).one_or_none()
            if user:
                user.last_quiz_sent_at = datetime.utcnow()
                user.next_random_quiz_at = next_quiz_at
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error updating quiz schedule for user {user_id}: {str(e)}")