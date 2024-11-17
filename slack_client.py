# slack_client.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
import logging
from slack_sdk import WebClient
from database_helpers import add_or_update_user, add_workspace
from utils import fetch_and_store_users

logging.basicConfig(level=logging.INFO)


# Slack bot token and client setup
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')


client = WebClient(token=SLACK_BOT_TOKEN)

# Slack signing secret and signature verifier setup
SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
signature_verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)

def get_slack_client():
    return client

def verify_slack_signature(request):
    """Verifies the signature of incoming Slack requests."""
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        logging.warning("Invalid Slack signature verification for request.")
        return False
    return True

def handle_slack_oauth_redirect(code):
    """Handles Slack OAuth redirect and workspace installation"""
    CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")
    try:
        # Exchange the authorization code for access tokens
        response = client.oauth_v2_access(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            code=code,
            redirect_uri=REDIRECT_URI
        )
        if response.get("ok"):
            team_id = response["team"]["id"]
            team_name = response["team"]["name"]

            # Add the workspace to the database
            add_workspace(team_id, team_name)

            # Fetch and store users for the new workspace
            fetch_and_store_users(team_id=team_id, update_existing=False)

            return True, "Installation Successful!"
        else:
            return False, response.get("error")
    except SlackApiError as e:
        print(f"Error during OAuth flow: {e.response['error']}")
        return False, "OAuth flow failed"
    except Exception as e:
        print(f"Unexpected error during OAuth flow: {str(e)}")
        return False, "OAuth flow failed due to unexpected error"

def handle_slack_event(event, team_id):
    """Handles Slack events related to user updates and team joins."""
    event_type = event.get('type')

    if event_type == "team_join":
        # A new user has joined the team
        user = event.get('user', {})
        user_id = user.get('id')
        name = user.get('real_name')
        profile = user.get('profile', {})
        image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

        # Add or update the user in the database
        add_or_update_user(user_id, name, image, team_id)

    elif event_type == "user_change":
        # A user's information has changed
        user = event.get('user', {})
        user_id = user.get('id')
        name = user.get('real_name')
        profile = user.get('profile', {})
        image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

        # Update the user's details in the database
        add_or_update_user(user_id, name, image, team_id)

    else:
        # Print unhandled event types for debugging purposes
        print(f"Unhandled event type: {event_type}")