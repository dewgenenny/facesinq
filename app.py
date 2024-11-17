from flask import Flask, request, jsonify
import os
import json
from db import engine, initialize_database  # Import the engine and initialization function
from models import Base # Ensure models are imported so they are registered
from database_helpers import update_user_opt_in, get_user_score, get_opted_in_user_count, has_user_opted_in, add_workspace, get_all_workspaces
app = Flask(__name__)

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facesinq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import the rest of your modules
from utils import fetch_and_store_users
from slack_sdk.errors import SlackApiError
from leaderboard import send_leaderboard
from slack_client import get_slack_client, verify_slack_signature
from game_manager import send_quiz_to_user, handle_quiz_response

with app.app_context():
    Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata
    initialize_database()  # Optional: add initial setup logic if needed
    fetch_and_store_users()




@app.route('/')
def index():
    return 'FaceSinq is running!'

@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    # initialise slack client
    client = get_slack_client()

    # verify signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403

    # Parse the payload
    payload = json.loads(request.form.get('payload'))
    action = payload['actions'][0]
    user_id = payload['user']['id']
    selected_user_id = action['value']
    message_ts = payload['message']['ts']
    channel_id = payload['channel']['id']
    team_id = request.form.get('team_id')  # Extract team_id from the incoming Slack command

    if action['action_id'].startswith('quiz_response'):
        handle_quiz_response(user_id, selected_user_id, payload)

    elif action['action_id'] == 'next_quiz':
        # Handle the "Next Quiz" button click
        send_quiz_to_user(user_id, team_id)

        # Modify the original message to disable the "Next Quiz" button
        original_blocks = payload['message']['blocks']

        # Find the action block containing the "Next Quiz" button
        next_quiz_block = None
        for block in original_blocks:
            if block.get('block_id') == 'next_quiz_block':
                next_quiz_block = block
                break

        if next_quiz_block:
            for element in next_quiz_block['elements']:
                if element.get('action_id') == 'next_quiz':
                    element['action_id'] = 'disabled_next_quiz'
                    element['text']['text'] = "Next Quiz Sent"
                    element['style'] = 'primary'
                    break
        else:
            print("Next Quiz action block not found.")


        # Update the message
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=original_blocks,
                text="Here's your next quiz!"
            )
        except SlackApiError as e:
            print(f"Error updating message: {e.response['error']}")
    else:
        # Handle other actions if any
        return '', 200
    return '', 200
@app.route('/slack/commands', methods=['POST'])
def slack_commands():

    # Verify the request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403


    command = request.form.get('command')
    user_id = request.form.get('user_id')
    text = request.form.get('text').strip().lower()
    channel_id = request.form.get('channel_id')  # Extract channel_id from the incoming Slack command
    team_id = request.form.get('team_id')  # Extract team_id from the incoming Slack command

    if command == '/facesinq':
        if text == 'opt-in':
            update_user_opt_in(user_id, True)
            return jsonify(response_type='ephemeral', text='You have opted in to FaceSinq quizzes!'), 200
        elif text == 'opt-out':
            update_user_opt_in(user_id, False)
            return jsonify(response_type='ephemeral', text='You have opted out of FaceSinq quizzes.'), 200
        elif text == 'quiz':
            # Check if the user has opted in
            if not has_user_opted_in(user_id):
                return jsonify(response_type='ephemeral', text='You need to opt-in first using `/facesinq opt-in`.'), 200
            # Send a quiz to the user
            send_quiz_to_user(user_id, team_id)
            return jsonify(response_type='ephemeral', text='Quiz sent!'), 200
        elif text == 'stats':
            # Handle the stats command (we'll implement this in the next section)
            count = get_opted_in_user_count()
            return jsonify(response_type='ephemeral', text=f'There are {count} users opted in to FaceSinq quizzes.'), 200
        elif text == 'score':
            score = get_user_score(user_id)
            return jsonify(response_type='ephemeral', text=f'Your current score is {score}.'), 200
        elif text == 'leaderboard':
            print("Got leaderboard request. Channel: " + channel_id )
            send_leaderboard(channel_id, user_id)
            return jsonify(response_type='ephemeral', text=f'Leaderboard sent'), 200

    else:
            return jsonify(response_type='ephemeral', text="Usage: /facesinq [opt-in | opt-out | quiz | stats | leaderboard]"), 200

    return '', 404


@app.route('/slack/events', methods=['POST'])
def slack_events():
    # Get the request body and headers
    body = request.get_data()
    headers = request.headers

    # Parse the request body as JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {}

    # Handle URL verification challenge
    if data.get('type') == 'url_verification':
        challenge = data.get('challenge')
        return jsonify({'challenge': challenge}), 200

    # Verify the request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403

    # Handle event callbacks
    if data.get('type') == 'event_callback':
        event = data.get('event')
        # You can handle different event types here
        return '', 200

    # If the request doesn't match any known types
    return '', 404

@app.route('/slack/install', methods=['POST'])
def slack_install():
    # Assuming this route is triggered when the app is installed in a workspace
    team_id = request.form.get('team_id')
    team_name = request.form.get('team_name')

    add_workspace(team_id, team_name)

    return "App Installed Successfully", 200

if __name__ == '__main__':

    from utils import fetch_and_store_users
    from quiz_app import send_quiz
    from apscheduler.schedulers.background import BackgroundScheduler
    with app.app_context():
        Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata

    # Fetch users for all workspaces
    for workspace in get_all_workspaces():
        fetch_and_store_users(team_id=workspace.id)

    # Schedule the quiz and user update tasks
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store_users_for_all_workspaces, 'interval', hours=2, kwargs={'update_existing': True})
    scheduler.start()

    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
