# Job Application Agent 🤖

An AI-powered job application agent that finds relevant jobs, writes personalised emails, and sends them via Gmail — with your approval via Telegram.

## What it does

1. **Scrapes jobs** from Indeed, Welcome to the Jungle, and your company list
2. **Finds contact emails** via Hunter.io + pattern guessing
3. **Writes personalised emails** using Gemini 2.5 Flash
4. **Sends drafts to Telegram** — you approve or skip each one
5. **Sends approved emails** via Gmail with your CV attached
6. **Tracks everything** in a local SQLite database

---

## Setup (do this once)

### Step 1 — Install dependencies

```bash
cd ~/Desktop/job-agent
pip install -r requirements.txt
playwright install chromium
```

### Step 2 — Create your .env file

```bash
cp .env.template .env
```

Open `.env` and fill in your keys:

```
GEMINI_API_KEY=your_new_gemini_key_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
HUNTER_API_KEY=your_hunter_key_here
GMAIL_SENDER=mlacabidze4@gmail.com
GMAIL_SENDER_NAME=Mariam Latsabidze | AI Engineer
TELEGRAM_CHAT_ID=  ← fill in after Step 4
```

### Step 3 — Get your Telegram Chat ID

```bash
python get_telegram_id.py
```

Then open Telegram and send any message to **@mjobagent_bot**.
Copy the chat ID printed in Terminal into your `.env` file.

### Step 4 — Set up Gmail OAuth

```bash
python setup_gmail.py
```

This opens your browser to authorise Gmail access.
You'll need to set up a Google Cloud project first — see instructions in setup_gmail.py.

### Step 5 — Update your CV path

Open `config.py` and update this line:
```python
"cv_path": "~/Desktop/Mariam_Latsabidze_CV_v5.docx",
```
Make sure the path points to your actual CV file.

### Step 6 — Update your company Excel list path

```python
COMPANY_LIST_PATH = "~/Desktop/Mariam_Job_Search_2026_v3.xlsx"
```

---

## Running the agent

### Manual run (recommended first time)

```bash
cd ~/Desktop/job-agent

# Dry run first — see what it would do without sending anything
python main.py --dry-run

# Real run
python main.py
```

### Run the Telegram bot (keep running in a separate Terminal)

```bash
python telegram_bot.py
```

### Schedule daily runs (runs automatically at 8am)

```bash
crontab -e
```

Add this line:
```
0 8 * * * cd ~/Desktop/job-agent && /usr/bin/python3 main.py >> ~/Desktop/job-agent/agent.log 2>&1
```

---

## Using the Telegram bot

When the agent finds new jobs, it sends each draft to your Telegram bot:

```
📧 New Application Draft
━━━━━━━━━━━━━━━━━━━━
🏢 Company: Empatica
💼 Role: Junior AI Engineer
📬 To: jobs@empatica.com
━━━━━━━━━━━━━━━━━━━━
Subject: Your WiFi cancer detection work & Empatica's mission

Dear Empatica team...
━━━━━━━━━━━━━━━━━━━━
📎 CV attached: Yes

[✅ Approve & Send]  [❌ Skip]
```

Tap **✅ Approve & Send** and the email is sent immediately.

---

## Checking stats

```bash
python main.py --stats
```

---

## Files

| File | Purpose |
|------|---------|
| `main.py` | Main agent — run this |
| `config.py` | Your profile & preferences |
| `scraper.py` | Job scraping from all platforms |
| `email_finder.py` | Finds HR contact emails |
| `email_writer.py` | Generates emails via Gemini |
| `telegram_bot.py` | Review queue on your phone |
| `gmail_sender.py` | Sends emails via Gmail API |
| `tracker.py` | SQLite application database |
| `setup_gmail.py` | One-time Gmail OAuth setup |
| `get_telegram_id.py` | Find your Telegram chat ID |
| `.env` | Your API keys (never share!) |
| `applications.db` | Your application history |

---

## Tips

- Run `--dry-run` first to check everything works before real sends
- Keep `telegram_bot.py` running in a separate Terminal tab for instant notifications
- The agent rotates through your company list daily — 20-30 companies per day
- Approved emails send immediately when you tap ✅ in Telegram
- Check `agent.log` if something goes wrong with the cron job
