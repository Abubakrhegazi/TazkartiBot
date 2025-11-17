# tazkarti_alert.py
import requests
import time
import sys
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
import threading
from flask import Flask

# --- Start a tiny Flask web server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Tazkarti Alert Bot is running on Render."

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Run Flask in a background thread
threading.Thread(target=run_flask).start()
# --- End Flask section ---


load_dotenv()

# === CONFIG ===
POLL_INTERVAL = 30  # seconds between checks
MATCH_URL = "https://www.tazkarti.com/data/matches-list-json.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")   
WATCH_TERMS = ["Ahly", "Al Ahly", "Al-Ahly", "الأهلي"]  # team name variants
TIMEZONE_OFFSET = 2  # Cairo = UTC+2
LOG_FILE = "alerts.log"
# =============


def cairo_time():
    """Return current Cairo time as datetime object."""
    return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)


def log(message):
    """Print and save message to local log file with timestamp."""
    timestamp = cairo_time().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_message + "\n")
    except Exception as e:
        print(f"{timestamp} ⚠️ Log write error: {e}")


def send_telegram_message(token, chat_id, text):
    """Send message to Telegram bot."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log("✅ Telegram message sent successfully.")
            return True
        else:
            log(f"⚠️ Telegram send failed: HTTP {r.status_code} - {r.text}")
            return False
    except Exception as e:
        log(f"❌ Telegram send error: {e}")
        return False


def check_matches_for_terms():
    """Fetch match list and detect Al Ahly matches."""
    try:
        r = requests.get(MATCH_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        log(f"🌐 Retrieved {len(data)} matches from Tazkarti feed.")
    except Exception as e:
        log(f"⚠️ Failed to fetch matches: {e}")
        return []

    found = []
    for m in data:
        text = " ".join([
            str(m.get("teamName1", "")),
            str(m.get("teamName2", "")),
            str(m.get("teamNameAr1", "")),
            str(m.get("teamNameAr2", "")),
            str(m.get("tournament", {}).get("nameEn", "")),
            str(m.get("tournament", {}).get("nameAr", "")),
        ]).lower()

        for term in WATCH_TERMS:
            if term.lower() in text:
                found.append(m)
                break
    return found


def format_match_message(match_obj):
    """Build alert message for Telegram."""
    team1 = match_obj.get("teamName1") or match_obj.get("teamNameAr1") or "Team 1"
    team2 = match_obj.get("teamName2") or match_obj.get("teamNameAr2") or "Team 2"
    date = match_obj.get("date", "Unknown date")
    kick = match_obj.get("kickOffTime", match_obj.get("kickoffTime", "Unknown"))
    stadium = match_obj.get("stadiumName", match_obj.get("stadiumNameAr", "Unknown"))
    mid = match_obj.get("matchId", "?")

    timestamp = cairo_time().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🚨 <b>ALERT: New Al Ahly Match Detected!</b>\n"
        f"🕒 <b>Detected at:</b> {timestamp} (Cairo Time)\n\n"
        f"⚽ <b>{team1}</b> vs <b>{team2}</b>\n"
        f"📅 Date: {date}\n"
        f"⏰ Kickoff: {kick}\n"
        f"🏟 Stadium: {stadium}\n"
        f"🆔 Match ID: {mid}\n\n"
        f"🎟 <a href='https://www.tazkarti.com/#/matches'>Book on Tazkarti</a>"
    )
    return msg


def main():
    log("🔄 Starting Tazkarti Alert Bot...")
    last_seen_ids = set()

    while True:
        matches = check_matches_for_terms()

        if not matches:
            log("⏳ No Al Ahly match found yet.")
        else:
            for m in matches:
                mid = m.get("matchId")
                if mid not in last_seen_ids:
                    message = format_match_message(m)
                    success = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
                    log(f"🚨 Alert triggered for match ID {mid} — success: {success}")
                    last_seen_ids.add(mid)
                else:
                    log(f"✅ Match {mid} already alerted previously.")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("👋 Bot stopped by user.")
        sys.exit(0)
