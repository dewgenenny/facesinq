import os
from tenacity import retry, stop_after_attempt, wait_exponential
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from db import engine, initialize_database
from models import Base
from database_helpers import add_or_update_user, does_user_exist, get_all_workspaces, get_workspace_access_token

# Slack API Client setup
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=5, max=60))
def fetch_users(team_id):
    """Fetch all users for a specific Slack team."""
    try:
        # Use database_helpers to get the workspace access token
        access_token = get_workspace_access_token(team_id)
        client = WebClient(token=access_token)  # Create a Slack client for this specific workspace

        # Call Slack API to fetch users
        response = client.users_list()
        if not response.get("ok"):
            raise Exception("Error in Slack API response")

        return response.get("members", [])

    except SlackApiError as e:
        if e.response.status_code == 429:  # HTTP 429 Too Many Requests
            retry_after = int(e.response.headers.get('Retry-After', 20))  # Slack tells you how long to wait
            print(f"Rate limited. Waiting for {retry_after} seconds before retrying.")
            raise e  # Let tenacity handle the retry timing with exponential backoff
        else:
            # Handle other Slack API errors
            print(f"Error fetching users from Slack for team_id {team_id}: {e.response['error']}")
            raise e

def fetch_and_store_users(team_id, update_existing=False):
    """
    Fetch users from Slack and store them in the database for a specific workspace.
    """
    if not team_id:
        raise ValueError("team_id must be provided to fetch and store users.")

    if does_user_exist(team_id) and not update_existing:
        print(f"Users already exist in the database for team {team_id}. Skipping fetch from Slack.")
        return

    try:
        users = fetch_users(team_id)  # Fetch users from Slack using the correct team ID
        print(f"Fetched {len(users)} users from Slack for team {team_id}")

        for user in users:
            if should_skip_user(user):
                print(f"Skipping user: {user.get('name')} ({user.get('id')})")
                continue

            user_id = user.get('id')
            name = user.get('real_name')
            profile = user.get('profile', {})
            image = profile.get('image_512') or profile.get('image_192') or profile.get('image_72', '')

            # Always use the correct team_id for updating/adding users
            print(f"Adding/updating user: {name} ({user_id}) for team {team_id}")
            add_or_update_user(user_id, name, image, team_id)

    except SlackApiError as e:
        print(f"Failed to fetch users from Slack: {e.response['error']}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")


def should_skip_user(user):
    """Determine if a Slack user should be skipped."""
    # Skip bots and deleted users
    if user.get('is_bot', False) or user.get('deleted', False):
        return True

    # Removed image filtering: Allow users even if they have no profile picture
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
