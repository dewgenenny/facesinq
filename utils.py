import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import sessionmaker
from db import Session, engine, initialize_database
from models import User, Base
from sqlalchemy.exc import IntegrityError

# Slack API Client setup
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=5, max=60))
def fetch_users():
    try:
        response = client.users_list()
        if not response.get("ok"):
            raise Exception("Error in Slack API response")
        return response.get("members", [])
    except SlackApiError as e:
        if e.response.status_code == 429:  # HTTP 429 Too Many Requests
            retry_after = int(e.response.headers.get('Retry-After', 20))  # Slack tells you how long to wait
            print(f"Rate limited. Waiting for {retry_after} seconds before retrying.")
            raise e  # Let tenacity handle the retry timing with exponential backoff
        else:
            # Handle other Slack API errors
            print(f"Error fetching users from Slack: {e.response['error']}")
            raise e

def fetch_and_store_users(update_existing=False):
    # Check if users already exist in the database
    with Session(bind=engine) as session:
        user_count = session.query(User).count()

        # If users exist and we are not updating, skip fetching
        if user_count > 0 and not update_existing:
            print("Users already exist in the database. Skipping fetch from Slack.")
            return

        # Otherwise, proceed with fetching users from Slack
        try:
            users = fetch_users()
            for user in users:
                user_id = user.get('id')
                name = user.get('real_name')

                profile = user.get('profile', {})
                image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

                # Skip users who are bots or deleted
                if user.get('is_bot', False) or user.get('deleted', False):
                    continue

                # Skip users who do not have a real profile photo set (placeholder)
                if not image or "secure.gravatar.com" in image:
                    continue

                try:
                    # Check if user already exists
                    existing_user = session.query(User).filter_by(id=user_id).one_or_none()
                    if existing_user:
                        # Update the existing user
                        existing_user.name = name
                        existing_user.image = image
                    else:
                        # Add the new user
                        new_user = User(id=user_id, name=name, image=image, opted_in=0)
                        session.add(new_user)
                    session.commit()

                except IntegrityError as e:
                    session.rollback()
                    print(f"Failed to insert/update user {user_id}: {str(e)}")

        except SlackApiError as e:
            print(f"Failed to fetch users from Slack: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    # Initialize database and create tables
    Base.metadata.create_all(bind=engine)  # This will create all tables if they don't exist
    initialize_database()  # Optional: add initial setup logic if needed

    # Fetch and store Slack users if not already present
    fetch_and_store_users()
