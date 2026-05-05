"""
gmail_sender.py
───────────────
Sends emails via Gmail API with CV attached.
First run: opens browser for OAuth — one-time only.
"""

import os
import base64
import pickle
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import CANDIDATE

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = Path.home() / "Desktop" / "job-agent" / "gmail_token.pickle"
CREDENTIALS_PATH = Path.home() / "Desktop" / "job-agent" / "gmail_credentials.json"
CV_PATH = Path(CANDIDATE["cv_path"]).expanduser()

SENDER_EMAIL = os.getenv("GMAIL_SENDER", "mlacabidze4@gmail.com")
SENDER_NAME  = os.getenv("GMAIL_SENDER_NAME", "Mariam Latsabidze | AI Engineer")


def get_gmail_service():
    """Authenticate and return Gmail API service. Opens browser on first run."""
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {CREDENTIALS_PATH}.\n"
                    "Please run setup_gmail.py first to set up Gmail OAuth."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


def build_email(to: str, subject: str, body: str, attach_cv: bool = True) -> str:
    """Build a MIME email with optional CV attachment. Returns base64url string."""
    msg = MIMEMultipart()
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    # Attach CV
    if attach_cv and CV_PATH.exists():
        with open(CV_PATH, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="Mariam_Latsabidze_CV.docx"',
        )
        msg.attach(part)
    elif attach_cv:
        print(f"[gmail] Warning: CV not found at {CV_PATH} — sending without attachment")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return raw


def send_email(to: str, subject: str, body: str, attach_cv: bool = True) -> bool:
    """
    Send an email via Gmail API.
    Returns True on success, False on failure.
    """
    try:
        service = get_gmail_service()
        raw_msg = build_email(to, subject, body, attach_cv)
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw_msg},
        ).execute()
        print(f"[gmail] Sent to {to} | Message ID: {result.get('id', '?')}")
        return True
    except HttpError as e:
        print(f"[gmail] HTTP error sending to {to}: {e}")
        return False
    except Exception as e:
        print(f"[gmail] Error sending to {to}: {e}")
        return False


def send_application(app: dict) -> bool:
    """Send a job application email from a tracked application record."""
    return send_email(
        to=app["contact_email"],
        subject=app["email_subject"],
        body=app["email_body"],
        attach_cv=True,
    )


if __name__ == "__main__":
    # Test — sends a test email to yourself
    print("Testing Gmail sender...")
    success = send_email(
        to=SENDER_EMAIL,
        subject="[TEST] Job Agent Email Test",
        body=(
            "This is a test email from your Job Agent.\n\n"
            "If you received this, Gmail OAuth is working correctly.\n\n"
            "— Job Agent"
        ),
        attach_cv=False,
    )
    print("Success!" if success else "Failed — check setup_gmail.py")
