"""
main.py (v3)
Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
- Ranks jobs by hire likelihood before selecting top 30
- Switched to gemini-1.5-flash (1500 req/day free)
- Fixed cold outreach subject lines
- Fixed Hunter NoneType bug
"""

import asyncio
import random
import time
import argparse
from datetime import datetime
from pathlib import Path

from config import EMAIL_SETTINGS, COMPANY_LIST_PATH, CANDIDATE
from scraper import scrape_all_jobs
from email_finder import find_email
from email_writer import write_email
from scorer import rank_jobs, explain_score
from tracker import (
    init_db, save_job, job_exists, save_draft, get_stats,
    already_contacted, count_sent_today, get_approved_unsent,
    mark_sent, record_contact,
)
from gmail_sender import send_application


def print_banner():
    print("\n" + "="*55)
    print("  Ã°ÂÂ¤Â  Job Agent Ã¢ÂÂ Starting Run")
    print(f"  Ã°ÂÂÂ  {datetime.now().strftime('%A %d %B %Y, %H:%M')}")
    print("="*55 + "\n")


def print_stats():
    stats = get_stats()
    print("\nÃ°ÂÂÂ Stats:")
    print(f"   Jobs found total:   {stats['total_jobs_found']}")
    print(f"   Applications sent:  {stats['total_sent']}")
    print(f"   Sent today:         {stats['sent_today']}")
    print(f"   Pending drafts:     {stats['pending_drafts']}")
    print(f"   Replies received:   {stats['replies_received']}\n")


async def notify_all_drafts(apps):
    if not apps:
        return
    import json
    from pathlib import Path
    drafts_file = Path(__file__).parent / 'pending_drafts.json'
    # Load existing drafts
    existing = []
    if drafts_file.exists():
        try:
            with open(drafts_file) as f:
                existing = json.load(f)
        except Exception:
            existing = []
    # Add new drafts (avoid duplicates by id)
    existing_ids = {d['id'] for d in existing}
    added = 0
    for app in apps:
        if app['id'] not in existing_ids:
            existing.append({
                'id': app['id'],
                'company': app['company'],
                'role': app['role'],
                'contact_email': app['contact_email'],
                'email_subject': app['email_subject'],
                'email_body': app['email_body'],
                'hire_score': app.get('hire_score', 0),
            })
            added += 1
    with open(drafts_file, 'w') as f:
        json.dump(existing, f, indent=2)
    print(f"[main] Saved {added} new drafts to pending_drafts.json ({len(existing)} total)")
    print(f"[main] Review at: https://mariamlats.github.io/job-agent/")


async def run_pipeline(dry_run=False, max_emails=None, show_ranking=False):
    print_banner()
    init_db()

    max_today = max_emails or EMAIL_SETTINGS["max_per_day"]
    sent_today = count_sent_today()

    if sent_today >= max_today:
        print(f"[main] Daily limit reached ({sent_today}/{max_today}). Skipping.")
        print_stats()
        return

    remaining = max_today - sent_today
    print(f"[main] Can send {remaining} more emails today (sent: {sent_today}/{max_today})")

    # Ã¢ÂÂÃ¢ÂÂ Step 1: Scrape Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    print("\n[main] Step 1: Scraping jobs...")
    company_list = str(Path(COMPANY_LIST_PATH).expanduser())
    all_jobs = await scrape_all_jobs(company_list_path=company_list)

    new_jobs = [j for j in all_jobs if not job_exists(j["job_id"])]
    print(f"[main] New jobs (not seen before): {len(new_jobs)}")

    if not new_jobs:
        print("[main] No new jobs found today.")
        print_stats()
        return

    for job in new_jobs:
        save_job(job)

    # Ã¢ÂÂÃ¢ÂÂ Step 2: Rank by hire likelihood Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    print(f"\n[main] Step 2: Ranking {len(new_jobs)} jobs by hire likelihood...")
    ranked_jobs = rank_jobs(new_jobs)

    if show_ranking:
        print("\nÃ°ÂÂÂ Top 10 jobs by hire likelihood:")
        for i, job in enumerate(ranked_jobs[:10], 1):
            print(f"\n  {i}. [{job['hire_score']:.2f}] {job['title']} @ {job['company']}")
            print(explain_score(job))

    # Ã¢ÂÂÃ¢ÂÂ Step 3: Deduplicate Ã¢ÂÂ max 1 per company, skip contacted Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    seen_companies = set()
    selected_jobs = []

    for job in ranked_jobs:  # already sorted best-first
        company_key = job["company"].lower().strip()
        if company_key in seen_companies:
            continue
        if already_contacted(job["company"], EMAIL_SETTINGS["cooldown_days"]):
            print(f"[main] Skipping {job['company']} Ã¢ÂÂ contacted recently")
            continue
        seen_companies.add(company_key)
        selected_jobs.append(job)
        if len(selected_jobs) >= remaining:
            break

    print(f"[main] Selected top {len(selected_jobs)} jobs after deduplication")
    print(f"[main] Score range: {selected_jobs[-1]['hire_score']:.2f} Ã¢ÂÂ {selected_jobs[0]['hire_score']:.2f}")

    # Ã¢ÂÂÃ¢ÂÂ Step 4: Generate drafts Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    print("\n[main] Step 4: Generating email drafts...")
    new_drafts = []
    gemini_calls = 0
    minute_start = time.time()

    for job in selected_jobs:
        company = job["company"]
        is_cold = job["platform"] == "cold_outreach"

        # Find real company email
        print(f"[main] [{job['hire_score']:.2f}] {job['title']} @ {company}")
        email_info = find_email(company, job.get("url", ""))
        contact_email = email_info.get("best", "")

        if not contact_email:
            print(f"   Ã¢ÂÂ  No email found Ã¢ÂÂ skipping")
            continue

        # Rate limiting: 4 calls per 65 seconds (gemini-1.5-flash: 15 RPM free)
        gemini_calls += 1
        if gemini_calls > 1 and gemini_calls % 14 == 0:
            elapsed = time.time() - minute_start
            wait = max(0, 65 - elapsed)
            if wait > 0:
                print(f"[main] Rate limit pause: {wait:.0f}s...")
                time.sleep(wait)
            minute_start = time.time()

        email = write_email(job, is_cold_outreach=is_cold)

        app = {
            "job_id": job["job_id"],
            "company": company,
            "role": job["title"],
            "contact_email": contact_email,
            "email_subject": email["subject"],
            "email_body": email["body"],
        }
        app_id = save_draft(app)
        app["id"] = app_id
        new_drafts.append(app)
        print(f"   Ã¢ÂÂ Draft #{app_id}: {email['subject'][:55]} Ã¢ÂÂ {contact_email}")

        # Small delay between calls
        time.sleep(2)

    print(f"\n[main] Generated {len(new_drafts)} new drafts")

    # Ã¢ÂÂÃ¢ÂÂ Step 5: Telegram Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    if not dry_run:
        print("\n[main] Step 5: Exporting all pending drafts to review page...")
        from tracker import get_pending_drafts
        all_pending = get_pending_drafts()
        await notify_all_drafts(all_pending)
        print(f"[main] {len(all_pending)} drafts available at https://mariamlats.github.io/job-agent/")
    elif dry_run:
        print("\n[main] DRY RUN Ã¢ÂÂ top drafts by hire likelihood:")
        for d in new_drafts:
            print(f"  [{d['id']}] {d['email_subject'][:55]} Ã¢ÂÂ {d['contact_email']}")

    # Ã¢ÂÂÃ¢ÂÂ Step 6: Send approved emails Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    print("\n[main] Step 6: Processing approved emails...")
    approved = get_approved_unsent()

    if not approved:
        print("[main] No approved emails waiting.")
    else:
        for app in approved:
            if count_sent_today() >= max_today:
                print("[main] Daily limit reached.")
                break
            if not dry_run:
                delay = random.randint(300, 900)
                print(f"[main] Waiting {delay//60}min before next send...")
                time.sleep(delay)
                success = send_application(app)
                if success:
                    mark_sent(app["id"])
                    record_contact(app["company"])
                    print(f"   Ã¢ÂÂ Sent: {app['email_subject'][:50]} Ã¢ÂÂ {app['contact_email']}")
                else:
                    print(f"   Ã¢ÂÂ Failed: {app['company']}")
            else:
                print(f"   [DRY RUN] Would send: {app['email_subject'][:50]} Ã¢ÂÂ {app['contact_email']}")

    if not dry_run:
        from telegram_bot import send_daily_digest
        await send_daily_digest()

    print_stats()
    print("\n[main] Ã¢ÂÂ Run complete!\n")


def main():
    parser = argparse.ArgumentParser(description="Job Application Agent")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max", type=int, default=None)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--show-ranking", action="store_true",
                        help="Show detailed score breakdown for top 10 jobs")
    args = parser.parse_args()

    if args.stats:
        init_db()
        print_stats()
        return

    asyncio.run(run_pipeline(
        dry_run=args.dry_run,
        max_emails=args.max,
        show_ranking=args.show_ranking,
    ))


if __name__ == "__main__":
    main()
