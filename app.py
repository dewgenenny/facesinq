from flask import Flask, request, jsonify
import os
import time
import json
from db import engine, initialize_database  # Import the engine and initialization function
from models import Base # Ensure models are imported so they are registered
from database_helpers import update_user_opt_in, get_user_score, get_opted_in_user_count, has_user_opted_in, add_workspace, get_all_workspaces, does_workspace_exist, get_user_access_token, reset_quiz_session
app = Flask(__name__)

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facesinq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

last_sync_times = {}

# Import the rest of your modules
from utils import fetch_and_store_users, fetch_and_store_users_for_all_workspaces, extract_user_id_from_text
from slack_sdk.errors import SlackApiError
from leaderboard import send_leaderboard
from slack_client import get_slack_client, verify_slack_signature, handle_slack_oauth_redirect, handle_slack_event, is_user_workspace_admin
from game_manager import send_quiz_to_user, handle_quiz_response

with app.app_context():
    Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata
    #initialize_database()  # Optional: add initial setup logic if needed
    #fetch_and_store_users_for_all_workspaces(update_existing=True)

@app.route('/slack/oauth_redirect', methods=['GET'])
def oauth_redirect():
    # Get authorization code from Slack
    code = request.args.get('code')

    # Handle the OAuth redirect using slack_client
    success, message = handle_slack_oauth_redirect(code)

    if success:
        print("received oauth request")
        return message, 200
    else:
        return jsonify({"error": message}), 400

@app.route('/')
def index():
    return 'FaceSinq is running!'


@app.route('/slack/actions', methods=['POST'])
def slack_actions():


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

    # Extract team_id from different possible locations in the payload
    team_id = None

    # 1. Try to extract team_id from the payload itself
    if 'team' in payload and 'id' in payload['team']:
        team_id = payload['team']['id']

    # 2. As a fallback, try extracting from request.form
    if not team_id:
        team_id = request.form.get('team_id')

    if not team_id:
        # Log an error for debugging if no team_id is found
        print(f"[ERROR] team_id could not be found in the request payload: {payload}")

    # initialise slack client
    client = get_slack_client(team_id)

    if action['action_id'].startswith('quiz_response'):
        handle_quiz_response(user_id, selected_user_id, payload, team_id)

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
            count = get_opted_in_user_count(team_id)
            return jsonify(response_type='ephemeral', text=f'There are {count} users opted in to FaceSinq quizzes.'), 200
        elif text == 'score':
            score = get_user_score(user_id)
            return jsonify(response_type='ephemeral', text=f'Your current score is {score}.'), 200
        elif text == 'leaderboard':
            print("Got leaderboard request. Channel: " + channel_id )
            send_leaderboard(channel_id=channel_id, user_id=user_id, team_id=team_id)
            return jsonify(response_type='ephemeral', text=f'Leaderboard sent'), 200
        elif text == "sync-users":
            handle_sync_users_command(user_id, team_id)
            return jsonify(response_type='ephemeral', text=f'Syncing users'), 200
        elif text == "reset-quiz":
            # Check if the user is a workspace admin
            if not is_user_workspace_admin(user_id, team_id):
                return jsonify({
                    'response_type': 'ephemeral',  # Only the user sees this response
                    'text': "You do not have the required permissions to perform this action. Only admins are allowed."
                }), 403

            # Extract target user ID from the text
            target_user_id = user_id  # Function to extract user ID from the command text
            if target_user_id:
                try:
                    reset_quiz_session(target_user_id)
                    return jsonify({"text": f"Quiz for user <@{target_user_id}> has been reset."})
                except Exception as e:
                    return jsonify({"text": f"Failed to reset quiz: {str(e)}"}), 500
            else:
                return jsonify({"text": "Please specify a valid user ID."}), 400
    elif command == "/facesinq-reset-quiz":
        # Check if the user is a workspace admin
        if not is_user_workspace_admin(user_id, team_id):
            return jsonify({
                'response_type': 'ephemeral',  # Only the user sees this response
                'text': "You do not have the required permissions to perform this action. Only admins are allowed."
            }), 403

        # Extract target user ID from the text
        target_user_id = extract_user_id_from_text(text)  # Function to extract user ID from the command text
        if target_user_id:
            try:
                reset_quiz_session(target_user_id)
                return jsonify({"text": f"Quiz for user <@{target_user_id}> has been reset."})
            except Exception as e:
                return jsonify({"text": f"Failed to reset quiz: {str(e)}"}), 500
        else:
            return jsonify({"text": "Please specify a valid user ID using the format @username."}), 400


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
        return jsonify({'error': 'invalid JSON'}), 400

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
        team_id = data.get('team_id')  # Extract the `team_id` from the request

        # Delegate event handling to slack_client
        if event:
            handle_slack_event(event, team_id)
            return '', 200

@app.route('/slack/install', methods=['POST'])
def slack_install():
    # Assuming this route is triggered when the app is installed in a workspace
    team_id = request.form.get('team_id')
    team_name = request.form.get('team_name')

    add_workspace(team_id, team_name)

    return "App Installed Successfully", 200

def handle_sync_users_command(user_id, team_id):
    """Handle the `/sync-users` command to refresh users in the workspace."""
    global last_sync_times  # Use the global dictionary to track last sync times
    current_time = time.time()
    rate_limit_interval = 3600  # 1 hour in seconds

    # Ensure the workspace is recorded in the database
    if not does_workspace_exist(team_id):
        # If the workspace is not found, add it to the database using available information
        print("No workspace found, trying to add")
        try:
            # Fetch the team info from Slack API to get team name and access token
            access_token = get_user_access_token(user_id)  # Get the user's access token
            client = get_slack_client()
            response = client.team_info()

            if not response.get('ok'):
                return jsonify({
                    'response_type': 'ephemeral',
                    'text': "Failed to retrieve workspace information from Slack. Please try again or contact support."
                })

            team_info = response.get('team', {})
            team_name = team_info.get('name', 'Unknown Workspace')

            # Add workspace to the database
            add_workspace(team_id, team_name, access_token)

        except SlackApiError as e:
            return jsonify({
                'response_type': 'ephemeral',
                'text': f"Failed to retrieve workspace information from Slack: {e.response['error']}"
            })
        except Exception as e:
            return jsonify({
                'response_type': 'ephemeral',
                'text': f"An unexpected error occurred while adding the workspace: {str(e)}"
            })

    # Rate limit check: Ensure the command is not called too often
    if team_id in last_sync_times:
        elapsed_time = current_time - last_sync_times[team_id]
        if elapsed_time < rate_limit_interval:
            remaining_time = rate_limit_interval - elapsed_time
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            return jsonify({
                'response_type': 'ephemeral',
                'text': f"Sync can be run only once per hour. Please try again in {minutes} minutes and {seconds} seconds."
            })

    # Update last sync time
    last_sync_times[team_id] = current_time

    # Start the user sync
    try:
        fetch_and_store_users(team_id, update_existing=True)
        return jsonify({
            'response_type': 'in_channel',
            'text': "User sync successfully started for your workspace."
        })
    except SlackApiError as e:
        return jsonify({
            'response_type': 'ephemeral',
            'text': f"Failed to start user sync: {e.response['error']}"
        })
    except Exception as e:
        return jsonify({
            'response_type': 'ephemeral',
            'text': f"An unexpected error occurred: {str(e)}"
        })


if __name__ == '__main__':

    from utils import fetch_and_store_users
    from quiz_app import send_quiz
    from apscheduler.schedulers.background import BackgroundScheduler
    if __name__ == '__main__':
        # with app.app_context():
        #     Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata

        # Fetch users for all workspaces
        # Fetch only if database and tables are newly created or updated
        fetch_and_store_users_for_all_workspaces(update_existing=True)

        # Schedule the quiz and user update tasks
        scheduler = BackgroundScheduler()
        scheduler.add_job(fetch_and_store_users_for_all_workspaces, 'interval', hours=1, kwargs={'update_existing': True})
        scheduler.start()

        port = int(os.environ.get('PORT', 3000))
        app.run(host='0.0.0.0', port=port)