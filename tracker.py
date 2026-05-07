"""
tracker.py
──────────
SQLite-based application tracker. Stores every job found, email drafted,
sent, and replied to. Prevents duplicate applications.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "applications.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          TEXT UNIQUE,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            url             TEXT,
            platform        TEXT,
            description     TEXT,
            salary          TEXT,
            language        TEXT,
            score           REAL,
            found_at        TEXT DEFAULT (datetime('now')),
            status          TEXT DEFAULT 'found'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          TEXT,
            company         TEXT,
            role            TEXT,
            contact_email   TEXT,
            email_subject   TEXT,
            email_body      TEXT,
            cv_attached     INTEGER DEFAULT 1,
            status          TEXT DEFAULT 'draft',
            telegram_msg_id INTEGER,
            drafted_at      TEXT DEFAULT (datetime('now')),
            sent_at         TEXT,
            replied_at      TEXT,
            followup_sent   INTEGER DEFAULT 0,
            notes           TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS companies_contacted (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company         TEXT UNIQUE,
            domain          TEXT,
            last_contacted  TEXT,
            times_contacted INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print(f"[tracker] Database ready at {DB_PATH}")


# ── Jobs ──────────────────────────────────────────────────────────────────────

def save_job(job: dict) -> bool:
    """Save a job. Returns True if new, False if already exists."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO jobs (job_id, title, company, location, url, platform,
                              description, salary, language, score)
            VALUES (:job_id, :title, :company, :location, :url, :platform,
                    :description, :salary, :language, :score)
        """, job)
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def job_exists(job_id: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


# ── Applications ──────────────────────────────────────────────────────────────

def save_draft(app: dict) -> int:
    """Save a draft application. Returns the application ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO applications
            (job_id, company, role, contact_email, email_subject, email_body, status)
        VALUES
            (:job_id, :company, :role, :contact_email, :email_subject, :email_body, 'draft')
    """, app)
    app_id = c.lastrowid
    conn.commit()
    conn.close()
    return app_id


def update_telegram_msg_id(app_id: int, msg_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET telegram_msg_id = ? WHERE id = ?",
        (msg_id, app_id)
    )
    conn.commit()
    conn.close()


def mark_sent(app_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
        (app_id,)
    )
    conn.commit()
    conn.close()


def mark_approved(app_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET status = 'approved' WHERE id = ?",
        (app_id,)
    )
    conn.commit()
    conn.close()


def mark_rejected(app_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET status = 'rejected' WHERE id = ?",
        (app_id,)
    )
    conn.commit()
    conn.close()


def get_application(app_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_drafts() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE status = 'draft' ORDER BY drafted_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_approved_unsent() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE status = 'approved' ORDER BY drafted_at ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def count_sent_today() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) FROM applications
        WHERE status = 'sent'
        AND date(sent_at) = date('now')
    """)
    count = c.fetchone()[0]
    conn.close()
    return count


# ── Company cooldown ──────────────────────────────────────────────────────────

def already_contacted(company: str, cooldown_days: int = 30) -> bool:
    """Check if we've contacted this company within the cooldown period."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT last_contacted FROM companies_contacted WHERE company = ?",
        (company.lower().strip(),)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    last = datetime.fromisoformat(row["last_contacted"])
    return (datetime.now() - last).days < cooldown_days


def record_contact(company: str, domain: str = ""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO companies_contacted (company, domain, last_contacted, times_contacted)
        VALUES (?, ?, datetime('now'), 1)
        ON CONFLICT(company) DO UPDATE SET
            last_contacted = datetime('now'),
            times_contacted = times_contacted + 1
    """, (company.lower().strip(), domain))
    conn.commit()
    conn.close()


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status = 'sent'")
    total_sent = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status = 'sent' AND date(sent_at) = date('now')")
    sent_today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status = 'draft'")
    pending = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE replied_at IS NOT NULL")
    replies = c.fetchone()[0]

    conn.close()
    return {
        "total_jobs_found": total_jobs,
        "total_sent": total_sent,
        "sent_today": sent_today,
        "pending_drafts": pending,
        "replies_received": replies,
    }


if __name__ == "__main__":
    init_db()
    print("Stats:", get_stats())
