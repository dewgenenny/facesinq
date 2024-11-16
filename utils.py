# utils.py (refactor fetch_and_store_users)
from models import db, User
from slack_sdk import WebClient
import os
import time
from slack_sdk.errors import SlackApiError

def fetch_and_store_users():
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    retries = 5
    delay = 2

    for i in range(retries):
        try:
            response = client.users_list()
            for member in response['members']:
                if not member['is_bot'] and not member['deleted']:
                    user_id = member['id']
                    name = member['real_name']
                    image = member['profile'].get('image_192', '')

                    # Add user to DB
                    existing_user = User.query.get(user_id)
                    if not existing_user:
                        new_user = User(id=user_id, name=name, image=image)
                        db.session.add(new_user)

            db.session.commit()
            break
        except SlackApiError as e:
            if e.response['error'] == 'ratelimited':
                print("Rate limited. Retrying...")
                time.sleep(delay)
                delay *= 2  # exponential backoff
            else:
                print(f"Error fetching users: {e.response['error']}")
                break
