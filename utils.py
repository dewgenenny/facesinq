# utils.py (refactor fetch_and_store_users)
from models import db, User
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

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

                # Check if user already exists
                existing_user = User.query.get(user_id)
                if not existing_user:
                    # Create a new user
                    new_user = User(id=user_id, name=name, image=image)
                    db.session.add(new_user)

        db.session.commit()
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
