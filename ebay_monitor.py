"""
eBay Listing Monitor → Telegram Bot
=====================================
Мониторит листинги eBay и шлёт уведомления в Telegram при изменениях.

НАСТРОЙКА (один раз):
1. Создай бота: напиши @BotFather в Telegram → /newbot → скопируй токен
2. Узнай свой chat_id: напиши @userinfobot в Telegram
3. Вставь токен и chat_id ниже
4. Добавь ссылки на листинги в LISTINGS
5. Установить зависимости: pip install requests beautifulsoup4
6. Запустить: python ebay_monitor.py
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime

# ============================================================
#  НАСТРОЙКИ — ЗАПОЛНИ ЭТО
# ============================================================

TELEGRAM_TOKEN = "8723010638:AAFYkdY1TcAN4iNWo3BXFKWZp2uoYiMBfTI"   # от @BotFather
TELEGRAM_CHAT_ID = "1618321073"    # от @userinfobot

# Ссылки на листинги eBay (можно добавлять сколько угодно)
LISTINGS = [
    "https://www.ebay.com/itm/366298371227
    "https://www.ebay.com/itm/366293770029
    # "https://www.ebay.com/itm/366293774209
]

CHECK_INTERVAL_MINUTES = 15   # как часто проверять (в минутах)
STATE_FILE = "ebay_state.json" # файл для хранения предыдущих данных

# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def send_telegram(message: str):
    """Отправляет сообщение в Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if not resp.ok:
            print(f"[Telegram error] {resp.text}")
    except Exception as e:
        print(f"[Telegram error] {e}")


def get_listing_data(url: str) -> dict | None:
    """Парсит страницу листинга и возвращает данные."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[HTTP {resp.status_code}] {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        data = {"url": url}

        # Название товара
        title_tag = soup.find("h1", {"class": "x-item-title__mainTitle"})
        if not title_tag:
            title_tag = soup.find("h1", itemprop="name")
        data["title"] = title_tag.get_text(strip=True) if title_tag else "Без названия"

        # Цена
        price_tag = (
            soup.find("div", {"class": "x-price-primary"}) or
            soup.find("span", itemprop="price") or
            soup.find("span", {"class": "ux-textspans", "id": lambda x: x and "prcIsum" in str(x)})
        )
        data["price"] = price_tag.get_text(strip=True) if price_tag else "—"

        # Статус (продан / активен)
        sold_tag = soup.find("div", {"class": "vim x-bin-action"})
        ended_tag = soup.find(string=lambda t: t and ("ended" in t.lower() or "sold" in t.lower()))
        if ended_tag:
            data["status"] = "🔴 Продан / Завершён"
        else:
            data["status"] = "🟢 Активен"

        # Количество проданных (если есть)
        sold_count_tag = soup.find("span", {"class": "ux-textspans--SECONDARY"})
        if sold_count_tag and "sold" in sold_count_tag.get_text().lower():
            data["sold_count"] = sold_count_tag.get_text(strip=True)
        else:
            data["sold_count"] = None

        # Количество ставок (аукцион)
        bids_tag = soup.find("span", {"class": "ux-summary__count"})
        if not bids_tag:
            bids_tag = soup.find(string=lambda t: t and "bid" in t.lower() and t.strip()[0].isdigit())
        data["bids"] = bids_tag.get_text(strip=True) if bids_tag and hasattr(bids_tag, "get_text") else None

        return data

    except Exception as e:
        print(f"[Parse error] {url}: {e}")
        return None


def load_state() -> dict:
    """Загружает сохранённые данные из файла."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """Сохраняет данные в файл."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_and_notify(state: dict) -> dict:
    """Проверяет все листинги и отправляет уведомления при изменениях."""
    for url in LISTINGS:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверяю: {url[:60]}...")
        current = get_listing_data(url)

        if not current:
            continue

        prev = state.get(url)

        if prev is None:
            # Первый запуск — просто сохраняем, не шлём уведомление
            print(f"  → Сохранён: {current['title'][:50]} | {current['price']} | {current['status']}")
            state[url] = current
            continue

        # Сравниваем с предыдущими данными
        changes = []

        if current["price"] != prev.get("price"):
            changes.append(f"💰 Цена: <b>{prev.get('price')}</b> → <b>{current['price']}</b>")

        if current["status"] != prev.get("status"):
            changes.append(f"📦 Статус: {prev.get('status')} → {current['status']}")

        if current["sold_count"] and current["sold_count"] != prev.get("sold_count"):
            changes.append(f"🛒 Продано: {prev.get('sold_count')} → {current['sold_count']}")

        if current["bids"] and current["bids"] != prev.get("bids"):
            changes.append(f"🔨 Ставки: {prev.get('bids')} → {current['bids']}")

        if changes:
            msg = (
                f"🔔 <b>Изменение в листинге!</b>\n\n"
                f"📌 {current['title'][:80]}\n\n"
                + "\n".join(changes) +
                f"\n\n🔗 <a href='{url}'>Открыть листинг</a>"
            )
            send_telegram(msg)
            print(f"  → ИЗМЕНЕНИЕ! Уведомление отправлено.")
        else:
            print(f"  → Без изменений.")

        state[url] = current

        time.sleep(2)  # пауза между запросами

    return state


def main():
    print("=" * 50)
    print("  eBay Monitor → Telegram")
    print("=" * 50)
    print(f"  Листингов: {len(LISTINGS)}")
    print(f"  Интервал проверки: {CHECK_INTERVAL_MINUTES} мин")
    print("=" * 50)

    # Проверяем настройки
    if "ВАШ_ТОКЕН" in TELEGRAM_TOKEN or "ВАШ_CHAT" in TELEGRAM_CHAT_ID:
        print("\n❌ ОШИБКА: Заполни TELEGRAM_TOKEN и TELEGRAM_CHAT_ID в начале файла!")
        return

    if not any("ebay.com/itm" in url for url in LISTINGS):
        print("\n❌ ОШИБКА: Добавь реальные ссылки на листинги в список LISTINGS!")
        return

    send_telegram("✅ <b>eBay Monitor запущен!</b>\nБуду следить за изменениями в твоих листингах.")
    print("\n✅ Telegram-уведомление отправлено. Начинаю мониторинг...\n")

    state = load_state()

    while True:
        state = check_and_notify(state)
        save_state(state)
        print(f"\n⏳ Следующая проверка через {CHECK_INTERVAL_MINUTES} мин...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
