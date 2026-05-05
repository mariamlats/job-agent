"""
get_telegram_id.py
──────────────────
Run this once to find your Telegram chat ID.
Send any message to your bot after running this,
and it will print your chat ID.
"""

import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "unknown"
    print(f"\n✅ Found your Telegram Chat ID!")
    print(f"   Chat ID:  {chat_id}")
    print(f"   Username: @{username}")
    print(f"\nAdd this to your .env file:")
    print(f"   TELEGRAM_CHAT_ID={chat_id}")
    print("\nYou can now stop this script (Ctrl+C)\n")
    await update.message.reply_text(
        f"✅ Got it! Your chat ID is: `{chat_id}`\n\n"
        f"Add this to your .env file:\n`TELEGRAM_CHAT_ID={chat_id}`",
        parse_mode="Markdown",
    )


def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env file")
        return

    print("🤖 Bot is running...")
    print("Send ANY message to your Telegram bot (@mjobagent_bot) now.")
    print("Press Ctrl+C to stop.\n")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
