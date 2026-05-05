"""
main.py (v3)
────────────
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
    print("  🤖  Job Agent — Starting Run")
    print(f"  📅  {datetime.now().strftime('%A %d %B %Y, %H:%M')}")
    print("="*55 + "\n")


def print_stats():
    stats = get_stats()
    print("\n📊 Stats:")
    print(f"   Jobs found total:   {stats['total_jobs_found']}")
    print(f"   Applications sent:  {stats['total_sent']}")
    print(f"   Sent today:         {stats['sent_today']}")
    print(f"   Pending drafts:     {stats['pending_drafts']}")
    print(f"   Replies received:   {stats['replies_received']}\n")


async def notify_all_drafts(apps):
    if not apps:
        return
    print(f"[main] Sending {len(apps)} drafts to Telegram...")
    from telegram_bot import notify_draft
    for app in apps:
        await notify_draft(app)
        await asyncio.sleep(0.5)


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

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
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

    # ── Step 2: Rank by hire likelihood ──────────────────────────────────────
    print(f"\n[main] Step 2: Ranking {len(new_jobs)} jobs by hire likelihood...")
    ranked_jobs = rank_jobs(new_jobs)

    if show_ranking:
        print("\n📊 Top 10 jobs by hire likelihood:")
        for i, job in enumerate(ranked_jobs[:10], 1):
            print(f"\n  {i}. [{job['hire_score']:.2f}] {job['title']} @ {job['company']}")
            print(explain_score(job))

    # ── Step 3: Deduplicate — max 1 per company, skip contacted ──────────────
    seen_companies = set()
    selected_jobs = []

    for job in ranked_jobs:  # already sorted best-first
        company_key = job["company"].lower().strip()
        if company_key in seen_companies:
            continue
        if already_contacted(job["company"], EMAIL_SETTINGS["cooldown_days"]):
            print(f"[main] Skipping {job['company']} — contacted recently")
            continue
        seen_companies.add(company_key)
        selected_jobs.append(job)
        if len(selected_jobs) >= remaining:
            break

    print(f"[main] Selected top {len(selected_jobs)} jobs after deduplication")
    print(f"[main] Score range: {selected_jobs[-1]['hire_score']:.2f} – {selected_jobs[0]['hire_score']:.2f}")

    # ── Step 4: Generate drafts ───────────────────────────────────────────────
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
            print(f"   ⚠ No email found — skipping")
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
        print(f"   ✓ Draft #{app_id}: {email['subject'][:55]} → {contact_email}")

        # Small delay between calls
        time.sleep(2)

    print(f"\n[main] Generated {len(new_drafts)} new drafts")

    # ── Step 5: Telegram ──────────────────────────────────────────────────────
    if not dry_run and new_drafts:
        print("\n[main] Step 5: Sending drafts to Telegram...")
        await notify_all_drafts(new_drafts)
        print(f"[main] {len(new_drafts)} drafts sent — check your Telegram!")
    elif dry_run:
        print("\n[main] DRY RUN — top drafts by hire likelihood:")
        for d in new_drafts:
            print(f"  [{d['id']}] {d['email_subject'][:55]} → {d['contact_email']}")

    # ── Step 6: Send approved emails ──────────────────────────────────────────
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
                    print(f"   ✅ Sent: {app['email_subject'][:50]} → {app['contact_email']}")
                else:
                    print(f"   ❌ Failed: {app['company']}")
            else:
                print(f"   [DRY RUN] Would send: {app['email_subject'][:50]} → {app['contact_email']}")

    if not dry_run:
        from telegram_bot import send_daily_digest
        await send_daily_digest()

    print_stats()
    print("\n[main] ✅ Run complete!\n")


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
