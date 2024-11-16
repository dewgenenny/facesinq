import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import sessionmaker
from db import Session
from models import User
from sqlalchemy.exc import IntegrityError

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
            time.sleep(retry_after)  # Wait for the specified duration
            raise e  # Raise the exception to trigger a retry with tenacity
        else:
            # Handle other Slack API errors
            print(f"Error fetching users from Slack: {e.response['error']}")
            raise e

def fetch_and_store_users():
    try:
        users = fetch_users()

        # Create a session to interact with the database
        session = Session()

        for user in users:
            user_id = user.get('id')
            name = user.get('name')
            image = user.get('profile', {}).get('image_192', '')

            try:
                # Try fetching the user first
                existing_user = session.query(User).filter_by(id=user_id).one_or_none()
                if existing_user:
                    # Update the existing user
                    existing_user.name = name
                    existing_user.image = image
                else:
                    # Add the new user
                    new_user = User(id=user_id, name=name, image=image, opted_in=0)
                    session.add(new_user)

                # Commit after each operation to avoid data loss in case of failure
                session.commit()

            except IntegrityError as e:
                session.rollback()  # Rollback in case of an error
                print(f"Failed to insert/update user {user_id}: {str(e)}")

        # Close the session after finishing all operations
        session.close()

    except SlackApiError as e:
        print(f"Failed to fetch users from Slack due to rate limiting: {e}")

