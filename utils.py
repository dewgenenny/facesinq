from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import os

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)

def fetch_and_store_users():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    try:
        response = client.users_list()
        for member in response['members']:

            if not member['is_bot'] and not member['deleted']:
                user_id = member['id']
                name = member['real_name']
                c.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)', (user_id, name))
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
    conn.commit()
    conn.close()
