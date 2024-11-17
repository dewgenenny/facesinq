# slack_client.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
import logging

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