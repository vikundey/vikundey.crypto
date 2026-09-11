import json
import os
import urllib.parse
import urllib.request

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


API_KEY = os.environ.get("TWELVE_DATA_API_KEY")

if not API_KEY:
    raise RuntimeError("TWELVE_DATA_API_KEY is missing")


KYIV = ZoneInfo("Europe/Kyiv")


SYMBOLS = {
    "EURUSD": "EUR/USD",
    "XAUUSD": "XAU/USD",
    "BTC": "BTC/USD",
}


CALENDAR_PATH = Path("data/calendar.json")
OUTPUT_PATH = Path("data/market_reaction.json")


def load_calendar():
    if not CALENDAR_PATH.exists():
        raise RuntimeError("data/calendar.json not found")

    return json.loads(
        CALENDAR_PATH.read_text(encoding="utf-8")
    )


def parse_event_datetime(event):
    candidates = [
        event.get("datetime"),
        event.get("date_time"),
        event.get("timestamp"),
        event.get("released_at"),
    ]

    for value in candidates:
        if not value:
            continue

        try:
            dt = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KYIV)
            else:
                dt = dt.astimezone(KYIV)

            return dt

        except ValueError:
            pass

    date_value = event.get("date")
    time_value = event.get("time")

    if date_value and time_value:
        try:
            return datetime.fromisoformat(
                f"{date_value}T{time_value}"
            ).replace(tzinfo=KYIV)

        except ValueError:
            pass

    return None


def find_latest_high_event(calendar):
    now = datetime.now(KYIV)

    events = calendar.get("events", [])

    high_events = []

    for event in events:
        impact = str(
            event.get("impact", "")
        ).lower()

        if impact != "high":
            continue

        event_dt = parse_event_datetime(event)

        if not event_dt:
            continue

        if event_dt > now:
            continue

        high_events.append(
            (event_dt, event)
        )

    if not high_events:
        return None, None

    high_events.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return high_events[0]


def fetch_timeseries(symbol, start_dt, end_dt):
    params = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "interval": "1min",
            "start_date": start_dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "end_date": end_dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "timezone": "Europe/Kyiv",
            "apikey": API_KEY,
        }
    )

    url = (
        "https://api.twelvedata.com/time_series?"
        + params
    )

    with urllib.request.urlopen(
        url,
        timeout=30,
    ) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )

    if data.get("status") == "error":
        raise RuntimeError(
            data.get("message", str(data))
        )

    values = data.get("values", [])

    if not values:
        raise RuntimeError(
            f"No time series data for {symbol}"
        )

    parsed = []

    for row in values:
        try:
            dt = datetime.strptime(
                row["datetime"],
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=KYIV)

            parsed.append(
                {
                    "datetime": dt,
                    "close": float(
                        row["close"]
                    ),
                }
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ):
            continue

    parsed.sort(
        key=lambda row: row["datetime"]
    )

    return parsed


def nearest_price(
    rows,
    target_dt,
    tolerance_minutes=5,
):
    if not rows:
        return None

    nearest = min(
        rows,
        key=lambda row: abs(
            row["datetime"] - target_dt
        ),
    )

    difference = abs(
        nearest["datetime"] - target_dt
    )

    if difference > timedelta(
        minutes=tolerance_minutes
    ):
        return None

    return nearest["close"]


def percent_change(start_price, end_price):
    if (
        start_price is None
        or end_price is None
        or start_price == 0
    ):
        return None

    return round(
        (
            (end_price - start_price)
            / start_price
        )
        * 100,
        4,
    )


def main():
    calendar = load_calendar()

    event_dt, event = find_latest_high_event(
        calendar
    )

    if not event:
        result = {
            "status": "no_recent_event",
            "updated_at": datetime.now(
                KYIV
            ).isoformat(),
            "timezone": "Europe/Kyiv",
            "event": None,
            "assets": {},
        }

        OUTPUT_PATH.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "No completed HIGH-impact event found."
        )

        return

    now = datetime.now(KYIV)

    target_15m = event_dt + timedelta(
        minutes=15
    )

    target_1h = event_dt + timedelta(
        hours=1
    )

    fetch_end = min(
        now,
        target_1h + timedelta(
            minutes=5
        ),
    )

    fetch_start = event_dt - timedelta(
        minutes=5
    )

    assets = {}

    for display_name, symbol in SYMBOLS.items():

        try:
            rows = fetch_timeseries(
                symbol,
                fetch_start,
                fetch_end,
            )

            release_price = nearest_price(
                rows,
                event_dt,
            )

            price_15m = (
                nearest_price(
                    rows,
                    target_15m,
                )
                if now >= target_15m
                else None
            )

            price_1h = (
                nearest_price(
                    rows,
                    target_1h,
                )
                if now >= target_1h
                else None
            )

            assets[display_name] = {
                "symbol": symbol,

                "release_price":
                    release_price,

                "m15_price":
                    price_15m,

                "m15_change_pct":
                    percent_change(
                        release_price,
                        price_15m,
                    ),

                "h1_price":
                    price_1h,

                "h1_change_pct":
                    percent_change(
                        release_price,
                        price_1h,
                    ),

                "status": "ok",
            }

            print(
                display_name,
                assets[display_name],
            )

        except Exception as error:
            assets[display_name] = {
                "symbol": symbol,
                "status": "error",
                "error": str(error),
            }

            print(
                f"ERROR {display_name}: "
                f"{error}"
            )

    event_name = (
        event.get("title")
        or event.get("name")
        or event.get("event")
        or "HIGH impact event"
    )

    result = {
        "status": "ok",
        "updated_at": datetime.now(
            KYIV
        ).isoformat(),

        "timezone": "Europe/Kyiv",

        "event": {
            "name": event_name,
            "impact": "high",
            "released_at":
                event_dt.isoformat(),
        },

        "assets": assets,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
