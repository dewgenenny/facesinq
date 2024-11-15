# utils.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3

# utils.py
def fetch_and_store_users():
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    try:
        response = client.users_list()
        for member in response['members']:
            if not member['is_bot'] and not member['deleted']:
                user_id = member['id']
                name = member['real_name']
                image = member['profile'].get('image_192', '')
                c.execute('INSERT OR IGNORE INTO users (id, name, image) VALUES (?, ?, ?)', (user_id, name, image))
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
    conn.commit()
    conn.close()
