"""
send_approved.py — triggered by GitHub Actions when user approves a draft
Usage: python send_approved.py <app_id> [edited_body]
"""
import sys
import json
from pathlib import Path
from tracker import get_application, mark_sent, record_contact
from gmail_sender import send_application

def main():
    app_id = int(sys.argv[1])
    edited_body = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

    app = get_application(app_id)
    if not app:
        print(f"[send_approved] App {app_id} not found in DB")
        return

    if edited_body:
        app['email_body'] = edited_body
        print(f"[send_approved] Using edited body for app {app_id}")

    print(f"[send_approved] Sending email to {app['contact_email']} at {app['company']}...")
    success = send_application(app)

    if success:
        mark_sent(app_id)
        record_contact(app['company'], app['contact_email'])
        print(f"[send_approved] Sent successfully!")
    else:
        print(f"[send_approved] Failed to send")

if __name__ == '__main__':
    main()
