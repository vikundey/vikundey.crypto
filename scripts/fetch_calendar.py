#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "calendar.json"
KYIV_TZ = ZoneInfo("Europe/Kyiv")

IMPACT_ORDER = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}

def fetch_json(url: str) -> list[dict]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "vikundey.crypto-calendar/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))

def normalize_event(item: dict) -> dict:
    dt_source = datetime.fromisoformat(item["date"])
    dt_kyiv = dt_source.astimezone(KYIV_TZ)
    return {
        "title": item.get("title", "").strip(),
        "country": item.get("country", "").strip(),
        "impact": item.get("impact", "").strip(),
        "forecast": item.get("forecast", "") or "",
        "previous": item.get("previous", "") or "",
        "actual": item.get("actual", "") or "",
        "date_iso": dt_kyiv.isoformat(),
        "date": dt_kyiv.strftime("%Y-%m-%d"),
        "day": dt_kyiv.strftime("%a").upper(),
        "time": dt_kyiv.strftime("%H:%M"),
        "timestamp": int(dt_kyiv.timestamp()),
        "impact_rank": IMPACT_ORDER.get(item.get("impact", ""), -1),
    }

def main() -> int:
    try:
        raw = fetch_json(SOURCE_URL)
    except Exception as exc:
        print(f"Calendar fetch failed: {exc}", file=sys.stderr)
        return 1

    events = [normalize_event(x) for x in raw if x.get("country") == "USD"]
    events.sort(key=lambda e: e["timestamp"])
    dates = [e["date"] for e in events]

    payload = {
        "source": "Forex Factory",
        "source_url": "https://www.forexfactory.com/calendar",
        "feed_url": SOURCE_URL,
        "timezone": "Europe/Kyiv",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "week_start": min(dates) if dates else None,
        "week_end": max(dates) if dates else None,
        "event_count": len(events),
        "events": events,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(events)} USD events to {OUTPUT_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
