"""
telegram_bot.py (v2)
────────────────────
Full review queue with:
- ✅ Approve & Send
- ❌ Skip
- ✏️ Edit (you reply with new text, bot updates and re-shows)
- Inline editing — reply to any draft with "edit: [new text]" to update
- Daily digest
- /stats, /pending, /help commands
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)
from tracker import (
    mark_approved, mark_rejected, get_application,
    update_telegram_msg_id, get_stats, get_pending_drafts,
    mark_sent, record_contact,
)
from gmail_sender import send_application
from tracker import mark_sent

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Track which app_id we're waiting to edit from each chat
_waiting_for_edit: dict[int, int] = {}  # chat_id -> app_id


# ── Formatting ────────────────────────────────────────────────────────────────

def format_draft(app: dict, edited: bool = False) -> str:
    tag = "✏️ *EDITED*\n" if edited else ""
    return (
        f"{tag}"
        f"📧 *Application Draft #{app['id']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 *Company:* {app['company']}\n"
        f"💼 *Role:* {app['role']}\n"
        f"📬 *To:* `{app['contact_email']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Subject:* {app['email_subject']}\n\n"
        f"{app['email_body']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📎 CV attached · _ID: {app['id']}_"
    )


def draft_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve & Send", callback_data=f"approve_{app_id}"),
            InlineKeyboardButton("❌ Skip", callback_data=f"reject_{app_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Body", callback_data=f"edit_body_{app_id}"),
            InlineKeyboardButton("📝 Edit Subject", callback_data=f"edit_subject_{app_id}"),
        ],
    ])


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 *Job Agent Bot*\n\n"
        f"Your chat ID: `{chat_id}`\n\n"
        f"Add to your .env:\n`TELEGRAM_CHAT_ID={chat_id}`\n\n"
        f"*Commands:*\n"
        f"/stats — current stats\n"
        f"/pending — show pending drafts\n"
        f"/help — this message\n\n"
        f"*How to edit a draft:*\n"
        f"1. Tap ✏️ Edit Body or 📝 Edit Subject\n"
        f"2. Reply with your new text\n"
        f"3. The draft updates automatically\n"
        f"4. Tap ✅ Approve & Send when ready",
        parse_mode="Markdown",
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    await update.message.reply_text(
        f"📊 *Stats*\n"
        f"Sent today: {stats['sent_today']}\n"
        f"Total sent: {stats['total_sent']}\n"
        f"Pending drafts: {stats['pending_drafts']}\n"
        f"Replies: {stats['replies_received']}\n"
        f"Jobs found: {stats['total_jobs_found']}",
        parse_mode="Markdown",
    )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drafts = get_pending_drafts()
    if not drafts:
        await update.message.reply_text("No pending drafts right now.")
        return
    lines = [f"*{len(drafts)} pending drafts:*\n"]
    for d in drafts[:10]:
        lines.append(f"• #{d['id']} {d['company']} — {d['role'][:30]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if "_" not in data:
        return

    parts = data.split("_")
    # Handle multi-part actions like edit_body_123 and edit_subject_123
    if data.startswith("edit_body_"):
        app_id = int(data.replace("edit_body_", ""))
        _waiting_for_edit[chat_id] = ("body", app_id)
        app = get_application(app_id)
        await query.message.reply_text(
            f"✏️ *Editing email body for #{app_id}*\n"
            f"Company: {app['company']}\n\n"
            f"Reply with your new email body text.\n"
            f"_Send /cancel to cancel._",
            parse_mode="Markdown",
        )
        return

    if data.startswith("edit_subject_"):
        app_id = int(data.replace("edit_subject_", ""))
        _waiting_for_edit[chat_id] = ("subject", app_id)
        app = get_application(app_id)
        await query.message.reply_text(
            f"📝 *Editing subject for #{app_id}*\n"
            f"Current: _{app['email_subject']}_\n\n"
            f"Reply with your new subject line.\n"
            f"_Send /cancel to cancel._",
            parse_mode="Markdown",
        )
        return

    # Simple actions: approve_123, reject_123
    action = parts[0]
    app_id = int(parts[-1])
    app = get_application(app_id)

    if not app:
        await query.edit_message_text("❌ Application not found.")
        return

    if action == "approve":
        mark_approved(app_id)
        success = send_application(app)
        if success:
            mark_sent(app_id)
            record_contact(app["company"])
            await query.edit_message_text(
                f"✅ *Sent!*\n"
                f"📧 {app['email_subject']}\n"
                f"🏢 {app['company']} → `{app['contact_email']}`",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"⚠️ *Approved but Gmail send failed*\n"
                f"Check Gmail OAuth setup.\n"
                f"Company: {app['company']}",
                parse_mode="Markdown",
            )

    elif action == "reject":
        mark_rejected(app_id)
        await query.edit_message_text(
            f"❌ *Skipped*\n{app['company']} — {app['role']}",
            parse_mode="Markdown",
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text replies — used for editing drafts."""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Check if we're waiting for an edit from this chat
    if chat_id in _waiting_for_edit:
        edit_type, app_id = _waiting_for_edit.pop(chat_id)
        app = get_application(app_id)

        if not app:
            await update.message.reply_text("❌ Application not found.")
            return

        # Update the database
        import sqlite3
        from pathlib import Path
        db_path = Path.home() / "Desktop" / "job-agent" / "applications.db"
        conn = sqlite3.connect(db_path)

        if edit_type == "body":
            conn.execute(
                "UPDATE applications SET email_body = ? WHERE id = ?",
                (text, app_id)
            )
            conn.commit()
            conn.close()
            # Reload updated app
            updated_app = get_application(app_id)
            await update.message.reply_text(
                f"✅ *Email body updated!*\n\n"
                f"Here's your updated draft:",
                parse_mode="Markdown",
            )
            await update.message.reply_text(
                format_draft(updated_app, edited=True),
                parse_mode="Markdown",
                reply_markup=draft_keyboard(app_id),
            )

        elif edit_type == "subject":
            conn.execute(
                "UPDATE applications SET email_subject = ? WHERE id = ?",
                (text, app_id)
            )
            conn.commit()
            conn.close()
            updated_app = get_application(app_id)
            await update.message.reply_text(
                f"✅ *Subject updated!*\n\n"
                f"Here's your updated draft:",
                parse_mode="Markdown",
            )
            await update.message.reply_text(
                format_draft(updated_app, edited=True),
                parse_mode="Markdown",
                reply_markup=draft_keyboard(app_id),
            )
        return

    # Not waiting for edit — check for natural language commands
    text_lower = text.lower()
    if any(w in text_lower for w in ["pending", "how many", "drafts"]):
        await pending_command(update, context)
    elif any(w in text_lower for w in ["stats", "statistics", "sent"]):
        await stats_command(update, context)
    else:
        await update.message.reply_text(
            "Use /help to see available commands, or tap a button on a draft to interact with it."
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in _waiting_for_edit:
        _waiting_for_edit.pop(chat_id)
        await update.message.reply_text("✅ Edit cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


# ── Public functions for main.py ──────────────────────────────────────────────

async def send_draft_to_telegram(app: dict, bot: Bot) -> int | None:
    """Send a draft to Telegram for review. Returns message_id."""
    if not CHAT_ID:
        print("[telegram] TELEGRAM_CHAT_ID not set in .env")
        return None
    try:
        msg = await bot.send_message(
            chat_id=CHAT_ID,
            text=format_draft(app),
            parse_mode="Markdown",
            reply_markup=draft_keyboard(app["id"]),
        )
        update_telegram_msg_id(app["id"], msg.message_id)
        return msg.message_id
    except Exception as e:
        print(f"[telegram] Error sending draft #{app['id']}: {e}")
        return None


async def notify_draft(app: dict):
    """Send a single draft notification (non-blocking call from main.py)."""
    bot = Bot(token=BOT_TOKEN)
    async with bot:
        await send_draft_to_telegram(app, bot)


async def send_daily_digest():
    """Send daily stats digest."""
    if not CHAT_ID or not BOT_TOKEN:
        return
    stats = get_stats()
    text = (
        f"📊 *Daily Job Agent Digest*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Sent today: *{stats['sent_today']}*\n"
        f"📋 Pending drafts: *{stats['pending_drafts']}*\n"
        f"📬 Total sent: *{stats['total_sent']}*\n"
        f"💬 Replies: *{stats['replies_received']}*\n"
        f"🔍 Jobs found: *{stats['total_jobs_found']}*"
    )
    bot = Bot(token=BOT_TOKEN)
    async with bot:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")


# ── Bot runner ────────────────────────────────────────────────────────────────

def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def run_bot():
    """Run the bot in polling mode. Keep this running in a separate Terminal."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return
    print("[telegram] Bot starting — keep this Terminal open!")
    print("[telegram] The bot will receive your approve/skip/edit commands")
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
