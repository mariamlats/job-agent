"""
setup_gmail.py (v2)
───────────────────
One-time Gmail OAuth setup. Run this ONCE before using the agent.
"""

from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
CREDENTIALS_PATH = Path.home() / "Desktop" / "job-agent" / "gmail_credentials.json"
TOKEN_PATH = Path.home() / "Desktop" / "job-agent" / "gmail_token.pickle"


def setup():
    if not CREDENTIALS_PATH.exists():
        print(f"❌ gmail_credentials.json not found at {CREDENTIALS_PATH}")
        return

    print("Opening browser for Gmail authorisation...")
    print("Sign in with: mlacabidze4@gmail.com\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "wb") as f:
        pickle.dump(creds, f)

    print(f"\n✅ Gmail OAuth token saved to: {TOKEN_PATH}")
    print("You won't need to do this again unless the token expires.\n")
    print("✅ Setup complete! Run: python gmail_sender.py to send a test email.")


if __name__ == "__main__":
    setup()
