
import json
import os
import re
import urllib.request
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

URL = "https://www.iwind.at/map-webgl/spots/8296/overlay"
STATE_FILE = "wind_state.json"

# Northerly wind: 315° through 0° to 45°
def is_north(degrees):
    return degrees >= 315 or degrees <= 45


def get_wind():
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8")

    # Extract the live gauge belonging specifically to station 8296
    match = re.search(
        r'id="iwind-live-gauges-8296"[^>]*'
        r'data-gauge-payload=\'([^\']+)\'',
        html,
        re.DOTALL,
    )

    if not match:
        raise RuntimeError("Station 8296 live gauge data not found")

    return json.loads(unescape(match.group(1)))


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as file:
            return json.load(file)

    return {
        "north_count": 0,
        "north_alerted": False,
        "above_seven": False,
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def send_telegram(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
    }).encode()

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20):
        pass


def main():
    now = datetime.now(ZoneInfo("Europe/Vienna"))

    if not (9 <= now.hour < 18):
        print("Outside alert hours")
        return

    wind = get_wind()

    direction = float(wind["direction_deg"])
    speed = float(wind["wind_speed"])

    # Assumption to verify: iWind speed is reported in km/h.
    # If it is km/h, convert to knots.
    speed_knots = speed

    north = is_north(direction)
    state = load_state()

    print(f"Direction: {direction}°, speed: {speed_knots:.1f} knots")

      if north:
        state["north_count"] = min(state["north_count"] + 1, 2)
      else:
        state["north_count"] = 0
        state["north_alerted"] = False
        state["above_seven"] = False

    if north and state["north_count"] >= 2 and not state["north_alerted"]:
        send_telegram(
            f"🌬️ Achensee: Northerly wind starting!\n"
            f"Direction: {direction:.0f}°\n"
            f"Speed: {speed_knots:.1f} knots"
        )
        state["north_alerted"] = True

    above_seven = north and speed_knots >= 7

    if above_seven and not state["above_seven"]:
        send_telegram(
            f"🏄 Achensee: Northerly wind has reached 7 knots!\n"
            f"Direction: {direction:.0f}°\n"
            f"Speed: {speed_knots:.1f} knots"
        )

    state["above_seven"] = above_seven
    save_state(state)


if __name__ == "__main__":
    import urllib.parse
    main()
