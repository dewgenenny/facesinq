# utils.py

from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from db import Session
from models import User
import os
import time

@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=5, max=60))
def fetch_and_store_users():
    # Fetch users from Slack API
    # Initialize the Slack client
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        response = client.users_list()
        if not response.get("ok"):
            raise Exception("Error in Slack API response")

        users = response.get("members", [])

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
                    #print(f"User {user_id} updated successfully.")
                else:
                    # Add the new user
                    new_user = User(id=user_id, name=name, image=image, opted_in=0)
                    session.add(new_user)
                    #print(f"User {user_id} inserted successfully.")

                # Commit after each operation to avoid data loss in case of failure
                session.commit()

            except IntegrityError as e:
                session.rollback()  # Rollback in case of an error
                print(f"Failed to insert/update user {user_id}: {str(e)}")

        # Close the session after finishing all operations
        session.close()

    except SlackApiError as e:
        if e.response['error'] == 'ratelimited':
            # Slack rate-limited you, back off for the specific amount of time
            retry_after = int(e.response.headers.get('Retry-After', 20))
            print(f"Rate limited. Retrying after {retry_after} seconds.")
            time.sleep(retry_after)
            raise e
        else:
            # Handle other Slack API errors
            print(f"Error fetching users from Slack: {e.response['error']}")
            raise e

if __name__ == "__main__":
    fetch_and_store_users()
