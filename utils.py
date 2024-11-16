from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from slack_sdk.errors import SlackApiError
from models import db, User
from slack_sdk import WebClient
import os

# Tenacity retry decorator
@retry(
    stop=stop_after_attempt(5),  # Stop retrying after 5 attempts
    wait=wait_exponential(multiplier=2, min=2, max=30),  # Exponential backoff (2s, 4s, 8s, 16s, 30s max)
    retry=retry_if_exception(lambda e: isinstance(e, SlackApiError) and e.response['error'] == 'ratelimited')
)
def fetch_and_store_users():
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    try:
        response = client.users_list()
        for member in response['members']:
            if not member['is_bot'] and not member['deleted']:
                user_id = member['id']
                name = member['real_name']
                image = member['profile'].get('image_192', '')

                # Check if user already exists in the database
                existing_user = User.query.get(user_id)

                if existing_user:
                    # Update the existing user's information if necessary
                    existing_user.name = name
                    existing_user.image = image
                else:
                    # Create a new user if it doesn't already exist
                    new_user = User(id=user_id, name=name, image=image)
                    db.session.add(new_user)

        # Commit changes to the database after processing all users
        db.session.commit()

    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
        raise  # Re-raise the exception to allow tenacity to handle retries
