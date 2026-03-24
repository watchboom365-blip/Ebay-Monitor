import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = "8723010638:AAFYkdY1TcAN4iNWo3BXFKWZp2uoYiMBfTI"
TELEGRAM_CHAT_ID = "1618321073"

LISTINGS = [
    "https://www.ebay.com/itm/366298371227",
    "https://www.ebay.com/itm/366293770029",
]

CHECK_INTERVAL_MINUTES = 15
STATE_FILE = "ebay_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if not resp.ok:
            print("[Telegram error] " + resp.text)
    except Exception as e:
        print("[Telegram error] " + str(e))


def get_listing_data(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print("[HTTP " + str(resp.status_code) + "] " + url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {"url": url}

        title_tag = soup.find("h1", {"class": "x-item-title__mainTitle"})
        if not title_tag:
            title_tag = soup.find("h1", itemprop="name")
        data["title"] = title_tag.get_text(strip=True) if title_tag else "No title"

        price_tag = (
            soup.find("div", {"class": "x-price-primary"}) or
            soup.find("span", itemprop="price")
        )
        data["price"] = price_tag.get_text(strip=True) if price_tag else "---"

        ended_tag = soup.find(string=lambda t: t and ("ended" in t.lower() or "sold" in t.lower()))
        data["status"] = "Sold/Ended" if ended_tag else "Active"

        sold_count_tag = soup.find("span", {"class": "ux-textspans--SECONDARY"})
        if sold_count_tag and "sold" in sold_count_tag.get_text().lower():
            data["sold_count"] = sold_count_tag.get_text(strip=True)
        else:
            data["sold_count"] = None

        return data

    except Exception as e:
        print("[Parse error] " + url + ": " + str(e))
        return None


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_and_notify(state):
    for url in LISTINGS:
        print("Checking: " + url)
        current = get_listing_data(url)

        if not current:
            continue

        prev = state.get(url)

        if prev is None:
            print("Saved: " + current["title"][:50])
            state[url] = current
            continue

        changes = []

        if current["price"] != prev.get("price"):
            changes.append("Price: " + str(prev.get("price")) + " to " + str(current["price"]))

        if current["status"] != prev.get("status"):
            changes.append("Status: " + str(prev.get("status")) + " to " + str(current["status"]))

        if current["sold_count"] and current["sold_count"] != prev.get("sold_count"):
            changes.append("Sold: " + str(prev.get("sold_count")) + " to " + str(current["sold_count"]))

        if changes:
            msg = (
                "eBay Alert!\n\n" +
                current["title"][:80] + "\n\n" +
                "\n".join(changes) +
                "\n\nLink: " + url
            )
            send_telegram(msg)
            print("Change detected! Notification sent.")
        else:
            print("No changes.")

        state[url] = current
        time.sleep(2)

    return state


def main():
    print("eBay Monitor starting...")
    print("Listings: " + str(len(LISTINGS)))

    send_telegram("eBay Monitor started! Watching " + str(len(LISTINGS)) + " listings.")
    print("Telegram notification sent. Starting monitoring...")

    state = load_state()

    while True:
        state = check_and_notify(state)
        save_state(state)
        print("Next check in " + str(CHECK_INTERVAL_MINUTES) + " minutes...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
