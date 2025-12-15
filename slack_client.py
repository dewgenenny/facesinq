# slack_client.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
import logging
from slack_sdk import WebClient
from database_helpers import add_or_update_user, add_workspace, get_workspace_access_token
from utils import fetch_and_store_users, should_skip_user

logger = logging.getLogger(__name__)

# Slack bot token and client setup
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set!")

client = WebClient(token=SLACK_BOT_TOKEN)

# Slack signing secret and signature verifier setup
SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
if not SLACK_SIGNING_SECRET:
    logger.error("SLACK_SIGNING_SECRET is not set!")
else:
    logger.info("SLACK_SIGNING_SECRET loaded successfully.")

signature_verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)

def get_slack_client(team_id=None):
    """
    Returns a Slack client for a specific workspace. If no team_id is provided, returns the default client.
    """
    if team_id:
        try:
            access_token = get_workspace_access_token(team_id)
            if access_token:
                logger.info(f"Establishing Slack client for team_id: {team_id}")
                return WebClient(token=access_token)
            else:
                logger.warning(f"No access token found for team_id: {team_id}. Falling back to default bot token.")
        except Exception as e:
            logger.error(f"Error retrieving access token for team_id {team_id}: {e}")

    logger.debug("Using default Slack client.")
    return WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))

def verify_slack_signature(request):
    """Verifies the signature of incoming Slack requests."""
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        logger.warning(f"Invalid Slack signature verification for request. Headers: {request.headers}")
        return False
    logger.debug("Slack signature verified successfully.")
    return True

def handle_slack_oauth_redirect(code):
    """Handles Slack OAuth redirect and workspace installation"""
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI")

    logger.info("Starting OAuth flow...")

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
            access_token = response["access_token"]

            logger.info(f"OAuth successful for workspace: {team_name} ({team_id})")

            # Add the workspace to the database with access_token
            add_workspace(team_id, team_name, access_token)

            # Fetch and store users for the new workspace
            logger.info(f"Triggering user fetch for team_id: {team_id}")
            fetch_and_store_users(team_id=team_id, update_existing=True)

            return True, "Installation Successful!"
        else:
            logger.error(f"OAuth failed: {response.get('error')}")
            return False, response.get("error")
    except SlackApiError as e:
        logger.error(f"Slack API Error during OAuth flow: {e.response['error']}")
        return False, "OAuth flow failed"
    except Exception as e:
        logger.exception(f"Unexpected error during OAuth flow: {str(e)}")
        return False, "OAuth flow failed due to unexpected error"


def handle_slack_event(event, team_id):
    """Handles Slack events related to user updates and team joins."""
    event_type = event.get('type')
    logger.info(f"Received Slack event: {event_type} for team_id: {team_id}")

    if event_type == "team_join" or event_type == "user_change":
        # Handle new user joins or profile updates, ensuring the correct team_id is passed
        user = event.get('user', {})
        if user:
            # Use should_skip_user() to determine if this user should be skipped
            if should_skip_user(user):
                logger.info(f"Skipping user from event {event_type}: {user.get('id', 'unknown')} due to check criteria.")
                return

            user_id = user.get('id')
            name = user.get('real_name')
            profile = user.get('profile', {})
            image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

            # Add or update the user only if they are valid
            logger.info(f"Adding/Updating user from event: {name} ({user_id})")
            add_or_update_user(user_id, name, image, team_id)

    else:
        # Print unhandled event types for debugging purposes
        logger.debug(f"Unhandled event type: {event_type}")

def is_user_workspace_admin(user_id, team_id):
    """Determine if a user is a workspace admin."""
    try:
        # Get the Slack client with the correct workspace access token
        client = get_slack_client(team_id)
        response = client.users_info(user=user_id)

        if response.get("ok"):
            user_info = response.get("user", {})
            is_admin = user_info.get("is_admin", False)
            is_owner = user_info.get("is_owner", False)
            return is_admin or is_owner
        else:
            print(f"Failed to get user info for user {user_id}: {response.get('error')}")
            return False

    except SlackApiError as e:
        print(f"Slack API error when fetching user info for user {user_id}: {e.response['error']}")
        return False