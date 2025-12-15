# utils.py
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from db import engine
from models import Base
from database_helpers import add_or_update_user, does_user_exist, get_all_workspaces, get_workspace_access_token
import re
import logging

logger = logging.getLogger(__name__)

# Slack API Client setup
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)


def extract_user_id_from_text(text):
    """Extracts the Slack user ID from the given command text."""
    try:
        text = text.strip().upper()
        # Slack user IDs are typically provided in the format <@USERID>
        match = re.search(r'<@([A-Z0-9]+)>', text)
        if match:
            return match.group(1)
        elif text.strip().startswith('U'):
            # Handle the case where the user ID is provided directly
            return text.strip()
        else:
            logger.warning(f"Unable to extract user ID from text: {text}")
            return None
    except Exception as e:
        logger.error(f"Exception while extracting user ID: {str(e)}")
        return None


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=5, max=60))
def fetch_users(team_id):
    """Fetch all users for a specific Slack team."""
    try:
        # Use database_helpers to get the workspace access token
        access_token = get_workspace_access_token(team_id)

        if not access_token:
            raise ValueError(f"No access token found for team_id: {team_id}")

        logger.info(f"Fetching users for team_id: {team_id} using access token: {access_token[:6]}...")

        # Create a Slack client for this specific workspace
        client = WebClient(token=access_token)

        # Call Slack API to fetch users
        response = client.users_list()

        # Log entire response for debugging purposes
        logger.debug(f"Slack API response for team_id {team_id}: {response}")

        if not response.get("ok"):
            raise Exception(f"Slack API response not OK: {response}")

        # Extract and return members list if the response is successful
        members = response.get("members", [])
        logger.info(f"Successfully fetched {len(members)} users for team_id {team_id}")

        return members

    except SlackApiError as e:
        if e.response.status_code == 429:  # HTTP 429 Too Many Requests
            retry_after = int(e.response.headers.get('Retry-After', 20))  # Slack tells you how long to wait
            logger.warning(f"Rate limited. Waiting for {retry_after} seconds before retrying.")
            raise e  # Let tenacity handle the retry timing with exponential backoff
        else:
            # Handle other Slack API errors
            logger.error(f"Slack API error for team_id {team_id}: {e.response['error']}")
            raise e

    except ValueError as e:
        logger.error(f"ValueError: {str(e)}")
        raise e

    except Exception as e:
        logger.exception(f"Unexpected error occurred while fetching users for team_id {team_id}: {str(e)}")
        raise e


def fetch_and_store_users(team_id, update_existing=False):
    """
    Fetch users from Slack and store them in the database for a specific workspace.
    """
    if not team_id:
        raise ValueError("team_id must be provided to fetch and store users.")

    # Check if users already exist in the DB and skip fetching if update is not needed
    if does_user_exist(team_id) and not update_existing:
        logger.info(f"Users already exist in the database for team {team_id}. Skipping fetch from Slack.")
        return

    try:
        users = fetch_users(team_id)  # Fetch users from Slack using the correct team ID
        logger.info(f"Fetched {len(users)} users from Slack for team {team_id}")

        for user in users:
            # Use the updated should_skip_user function to filter users more precisely
            if should_skip_user(user):
                logger.debug(f"Skipping user: {user.get('real_name', 'Unknown')} ({user.get('id')})")
                continue

            user_id = user.get('id')
            name = user.get('real_name')

            # Extract image URL with priority for higher resolution
            profile = user.get('profile', {})
            image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

            # Always use the correct team_id for updating/adding users
            try:
                logger.debug(f"Adding/updating user: {name} ({user_id}) for team {team_id}")
                add_or_update_user(user_id, name, image, team_id)  # Make sure `team_id` is passed correctly
            except Exception as e:
                logger.error(f"Failed to add/update user {user_id}: {str(e)}")

    except SlackApiError as e:
        logger.error(f"Failed to fetch users from Slack: {e.response['error']}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")




def should_skip_user(user):
    """Determine if a Slack user should be skipped."""
    # Skip bots and deleted users
    if user.get('is_bot', False) or user.get('deleted', False):
        return True

    # Extract the user's profile information
    profile = user.get('profile', {})

    # Get the image from the profile (attempt higher resolution first)
    image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

    # Skip users who do not have a real profile photo set (e.g., a placeholder like Gravatar)
    if not image or "secure.gravatar.com" in image:
        logger.debug(f"Discounting profile - image is: {image}")
        return True

    # If none of the above conditions are met, the user should not be skipped
    return False

def fetch_and_store_users_for_all_workspaces(update_existing=False):
    """Fetch and store users for all workspaces."""
    for workspace in get_all_workspaces():
        print(f"Updating users for workspace {workspace.name} ({workspace.id})")
        fetch_and_store_users(update_existing=update_existing, team_id=workspace.id)


if __name__ == '__main__':
    # Initialize database and create tables
    Base.metadata.create_all(bind=engine)  # This will create all tables if they don't exist
    #initialize_database()  # Optional: add initial setup logic if needed

    # Fetch and store Slack users if not already present
    #fetch_and_store_users()
