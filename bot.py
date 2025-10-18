# bot.py
# Requires: python-telegram-bot==20.6 (or similar v20+)
# Usage: set environment variable BOT_TOKEN with your BotFather token before running.

import os
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List

from telegram import Update, Chat, Message
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ---------- CONFIG ----------
BOT_TOKEN_ENV = "BOT_TOKEN"
PORT = os.environ.get("PORT", 8080)  # ✅ Added this for Railway
TIMEZONE = ZoneInfo("Africa/Lagos")  # user requested Africa/Lagos
OPEN_HOUR = 6   # 6:00 AM inclusive
CLOSE_HOUR = 18 # 6:00 PM exclusive
COOLDOWN = timedelta(minutes=5)  # per-user cooldown
COOLDOWN_MSG = "⏳ Please wait before requesting another signal. Signals are limited to one every 5 minutes."
OUTSIDE_WINDOW_MSG = "⏳ Signal window closed. Try again between 6AM and 6PM."
START_MESSAGE = (
    "🔥 Welcome to BC Crash Live Signals Bot!\n"
    "Send a message containing the word `Signal` (anywhere) to receive a BC Crash-style signal.\n"
    "Signals available between 6AM and 6PM (Africa/Lagos). Be responsible — trade wisely."
)

# Anti-spam group throttle (simple heuristic)
CHAT_SIGNAL_WINDOW_SEC = 30
CHAT_SIGNAL_LIMIT = 6
CHAT_THROTTLE_DURATION = 60

# ---------- STATE ----------
last_signal_by_user: Dict[int, datetime] = {}
last_signal_type_by_chat: Dict[int, str] = {}
chat_signal_timestamps: Dict[int, List[datetime]] = {}
chat_throttle_until: Dict[int, datetime] = {}

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Helpers ----------
def now_lagos() -> datetime:
    return datetime.now(TIMEZONE)

def in_signal_window(now: datetime) -> bool:
    return OPEN_HOUR <= now.hour < CLOSE_HOUR

def format_time_for_signal(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p") if hasattr(dt, "strftime") else dt.strftime("%I:%M %p")

def generate_odds() -> float:
    if random.random() < 0.20:
        value = random.uniform(2.20, 2.30)
    else:
        value = random.uniform(1.80, 2.15)
    return round(value, 2)

def choose_signal_type(chat_id: int) -> str:
    last = last_signal_type_by_chat.get(chat_id)
    if not last:
        choice = random.choice(["BUY", "SELL"])
    else:
        if random.random() < 0.6:
            choice = "SELL" if last == "BUY" else "BUY"
        else:
            choice = random.choice(["BUY", "SELL"])
    last_signal_type_by_chat[chat_id] = choice
    return choice

def human_like_time(now: datetime) -> datetime:
    r = random.random()
    if r < 0.6:
        offset = random.choice([0, 0, 1, 2, 3])
    elif r < 0.9:
        offset = random.randint(4, 10)
    else:
        offset = random.randint(5, 20)
    return now + timedelta(minutes=offset)

def build_signal_message(signal_type: str, odds: float, t: datetime) -> str:
    return (
        f"📈 Signal Type: {signal_type}\n"
        f"🎯 Odds: {odds:.2f}\n"
        f"🕒 Time: {format_time_for_signal(t)}\n"
        f"⚠️ Disclaimer: Trade wisely. Market behavior may change."
    )

def is_chat_throttled(chat_id: int, now: datetime) -> bool:
    until = chat_throttle_until.get(chat_id)
    return bool(until and until > now)

def register_chat_signal(chat_id: int, now: datetime):
    lst = chat_signal_timestamps.setdefault(chat_id, [])
    lst.append(now)
    cutoff = now - timedelta(seconds=CHAT_SIGNAL_WINDOW_SEC)
    chat_signal_timestamps[chat_id] = [ts for ts in lst if ts > cutoff]
    if len(chat_signal_timestamps[chat_id]) > CHAT_SIGNAL_LIMIT:
        chat_throttle_until[chat_id] = now + timedelta(seconds=CHAT_THROTTLE_DURATION)

# ---------- Handlers ----------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message
    if not msg or not msg.text:
        return
    if msg.from_user is None or msg.from_user.is_bot:
        return

    chat: Chat = msg.chat
    user_id = msg.from_user.id
    chat_id = chat.id
    now = now_lagos()

    if "signal" not in msg.text.lower():
        return

    if is_chat_throttled(chat_id, now):
        return

    if not in_signal_window(now):
        await msg.reply_text(OUTSIDE_WINDOW_MSG)
        return

    last_used = last_signal_by_user.get(user_id)
    if last_used and now < last_used + COOLDOWN:
        await msg.reply_text(COOLDOWN_MSG)
        return

    signal_type = choose_signal_type(chat_id)
    odds = generate_odds()
    signal_time = human_like_time(now)
    text = build_signal_message(signal_type, odds, signal_time)
    await msg.reply_text(text)

    last_signal_by_user[user_id] = now
    register_chat_signal(chat_id, now)

# ---------- Main ----------
def main():
    token = os.environ.get(BOT_TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"Environment variable {BOT_TOKEN_ENV} not set. Set it to your BotFather token."
        )

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_handler))
    signal_filter = filters.TEXT & filters.Regex(r"(?i)\bsignal\b")
    app.add_handler(MessageHandler(signal_filter, text_handler))

    logger.info("Starting BC Crash Signals Bot (Africa/Lagos time).")
    app.run_polling(poll_interval=3.0, allowed_updates=Update.ALL_TYPES)  # ✅ Modified this

if __name__ == "__main__":
    main()
