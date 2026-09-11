import json
import os
import urllib.parse
import urllib.request

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================
# SETTINGS
# ============================================================

FOREX_FACTORY_URL = (
    "https://nfs.faireconomy.media/"
    "ff_calendar_thisweek.json"
)

FRED_API_KEY = os.environ.get("FRED_API_KEY")

KYIV = ZoneInfo("Europe/Kyiv")

OUTPUT_PATH = Path("data/calendar.json")


# ============================================================
# FRED SERIES
# ============================================================
#
# CPI:
# CPIAUCSL   = Headline CPI, seasonally adjusted
# CPILFESL   = Core CPI, seasonally adjusted
#
# PPI:
# PPIFIS     = Final Demand PPI, seasonally adjusted
# PPIFES     = Core Final Demand PPI, seasonally adjusted
#
# Labour:
# UNRATE     = Unemployment Rate
# PAYEMS     = Total Nonfarm Payrolls
# ICSA       = Initial Claims
#
# Retail:
# RSAFS      = Retail Sales
# RSFSXMV    = Retail Sales excluding autos
#

FRED_CACHE = {}


# ============================================================
# HTTP
# ============================================================

def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "vikundey.crypto/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


# ============================================================
# FRED
# ============================================================

def fred_observations(series_id, limit=20):
    """
    Returns FRED values newest -> oldest.
    """

    if not FRED_API_KEY:
        return []

    cache_key = (series_id, limit)

    if cache_key in FRED_CACHE:
        return FRED_CACHE[cache_key]

    params = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
    )

    url = (
        "https://api.stlouisfed.org/"
        "fred/series/observations?"
        + params
    )

    try:
        data = get_json(url)

        observations = []

        for item in data.get(
            "observations",
            [],
        ):
            value = item.get("value")

            if not value or value == ".":
                continue

            try:
                observations.append(
                    {
                        "date": item.get("date"),
                        "value": float(value),
                    }
                )

            except ValueError:
                continue

        FRED_CACHE[cache_key] = observations

        return observations

    except Exception as error:
        print(
            f"FRED ERROR {series_id}: "
            f"{error}"
        )

        return []


def latest_value(series_id):
    rows = fred_observations(
        series_id,
        limit=3,
    )

    if not rows:
        return None

    return rows[0]["value"]


def percentage_change(
    series_id,
    periods=1,
):
    rows = fred_observations(
        series_id,
        limit=periods + 5,
    )

    if len(rows) <= periods:
        return None

    latest = rows[0]["value"]
    previous = rows[periods]["value"]

    if previous == 0:
        return None

    return (
        (latest - previous)
        / previous
        * 100
    )


def absolute_change(series_id):
    rows = fred_observations(
        series_id,
        limit=3,
    )

    if len(rows) < 2:
        return None

    return (
        rows[0]["value"]
        - rows[1]["value"]
    )


# ============================================================
# FORMATTING
# ============================================================

def format_percent(value):
    if value is None:
        return None

    rounded = round(value, 1)

    if rounded == -0.0:
        rounded = 0.0

    return f"{rounded:.1f}%"


def format_number(value):
    if value is None:
        return None

    return str(
        round(value, 1)
    )


def format_k(value):
    if value is None:
        return None

    return f"{round(value):d}K"


# ============================================================
# FRED → FOREX FACTORY EVENT MAPPING
# ============================================================

def get_fred_actual(title):
    """
    Returns:
        actual_string, source

    If event is not supported:
        None, None
    """

    normalized = (
        title
        .lower()
        .strip()
    )

    # --------------------------------------------------------
    # CORE CPI
    # --------------------------------------------------------

    if normalized in {
        "core cpi m/m",
        "core cpi mom",
    }:
        value = percentage_change(
            "CPILFESL",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    if normalized in {
        "core cpi y/y",
        "core cpi yoy",
    }:
        value = percentage_change(
            "CPILFESL",
            periods=12,
        )

        return (
            format_percent(value),
            "FRED",
        )


    # --------------------------------------------------------
    # HEADLINE CPI
    # --------------------------------------------------------

    if normalized in {
        "cpi m/m",
        "cpi mom",
    }:
        value = percentage_change(
            "CPIAUCSL",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    if normalized in {
        "cpi y/y",
        "cpi yoy",
    }:
        value = percentage_change(
            "CPIAUCSL",
            periods=12,
        )

        return (
            format_percent(value),
            "FRED",
        )


    # --------------------------------------------------------
    # CORE PPI
    # --------------------------------------------------------

    if normalized in {
        "core ppi m/m",
        "core ppi mom",
    }:
        value = percentage_change(
            "PPIFES",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    if normalized in {
        "core ppi y/y",
        "core ppi yoy",
    }:
        value = percentage_change(
            "PPIFES",
            periods=12,
        )

        return (
            format_percent(value),
            "FRED",
        )


    # --------------------------------------------------------
    # HEADLINE PPI
    # --------------------------------------------------------

    if normalized in {
        "ppi m/m",
        "ppi mom",
    }:
        value = percentage_change(
            "PPIFIS",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    if normalized in {
        "ppi y/y",
        "ppi yoy",
    }:
        value = percentage_change(
            "PPIFIS",
            periods=12,
        )

        return (
            format_percent(value),
            "FRED",
        )


    # --------------------------------------------------------
    # UNEMPLOYMENT RATE
    # --------------------------------------------------------

    if normalized in {
        "unemployment rate",
    }:
        value = latest_value(
            "UNRATE"
        )

        return (
            format_percent(value),
            "FRED",
        )


    # --------------------------------------------------------
    # NFP
    # --------------------------------------------------------

    if normalized in {
        "non-farm employment change",
        "nonfarm payrolls",
        "non-farm payrolls",
        "nfp",
    }:
        value = absolute_change(
            "PAYEMS"
        )

        return (
            format_k(value),
            "FRED",
        )


    # --------------------------------------------------------
    # INITIAL JOBLESS CLAIMS
    # --------------------------------------------------------

    if normalized in {
        "unemployment claims",
        "initial jobless claims",
        "initial claims",
    }:
        value = latest_value(
            "ICSA"
        )

        if value is None:
            return None, None

        # FRED stores persons,
        # calendar normally displays K.
        value = value / 1000

        return (
            format_k(value),
            "FRED",
        )


    # --------------------------------------------------------
    # RETAIL SALES
    # --------------------------------------------------------

    if normalized in {
        "retail sales m/m",
        "retail sales mom",
    }:
        value = percentage_change(
            "RSAFS",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    if normalized in {
        "core retail sales m/m",
        "core retail sales mom",
    }:
        value = percentage_change(
            "RSFSXMV",
            periods=1,
        )

        return (
            format_percent(value),
            "FRED",
        )


    return None, None


# ============================================================
# FOREX FACTORY
# ============================================================

def fetch_forex_factory():
    data = get_json(
        FOREX_FACTORY_URL
    )

    if not isinstance(data, list):
        raise RuntimeError(
            "Forex Factory returned "
            "invalid format."
        )

    return data


def parse_event_datetime(event):
    raw_date = event.get("date")

    if not raw_date:
        return None

    try:
        dt = datetime.fromisoformat(
            raw_date.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=KYIV
            )

        return dt.astimezone(
            KYIV
        )

    except ValueError:
        return None


# ============================================================
# MAIN
# ============================================================

def main():
    raw_events = fetch_forex_factory()

    events = []

    for event in raw_events:

        if event.get("country") != "USD":
            continue

        dt = parse_event_datetime(
            event
        )

        if not dt:
            continue

        title = (
            event.get("title")
            or ""
        )

        actual = (
            event.get("actual")
            or ""
        )

        actual_source = (
            "Forex Factory"
            if actual
            else ""
        )

        # ----------------------------------------------------
        # FRED FALLBACK
        # Only for events that already happened.
        # ----------------------------------------------------

        if (
            not actual
            and dt <= datetime.now(KYIV)
            and FRED_API_KEY
        ):
            fred_actual, source = (
                get_fred_actual(title)
            )

            if fred_actual:
                actual = fred_actual
                actual_source = source

                print(
                    f"FRED fallback: "
                    f"{title} = {actual}"
                )

        impact = (
            event.get("impact")
            or ""
        )

        impact_rank = {
            "High": 3,
            "Medium": 2,
            "Low": 1,
            "Holiday": 0,
        }.get(
            impact,
            0,
        )

        calendar_event = {
            "title": title,

            "country":
                event.get(
                    "country",
                    "",
                ),

            "impact":
                impact,

            "forecast":
                event.get(
                    "forecast",
                    "",
                )
                or "",

            "previous":
                event.get(
                    "previous",
                    "",
                )
                or "",

            "actual":
                actual,

            "actual_source":
                actual_source,

            "date_iso":
                dt.isoformat(),

            "date":
                dt.strftime(
                    "%Y-%m-%d"
                ),

            "day":
                dt.strftime(
                    "%a"
                ).upper(),

            "time":
                dt.strftime(
                    "%H:%M"
                ),

            "timestamp":
                int(
                    dt.timestamp()
                ),

            "impact_rank":
                impact_rank,
        }

        events.append(
            calendar_event
        )


    events.sort(
        key=lambda item:
            item["timestamp"]
    )


    if events:
        week_start = (
            events[0]["date"]
        )

        week_end = (
            events[-1]["date"]
        )

    else:
        week_start = ""
        week_end = ""


    result = {
        "source":
            "Forex Factory + FRED",

        "timezone":
            "Europe/Kyiv",

        "updated_at":
            datetime.now(
                KYIV
            ).isoformat(),

        "week_start":
            week_start,

        "week_end":
            week_end,

        "event_count":
            len(events),

        "events":
            events,
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
        f"Saved {len(events)} "
        f"USD events to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
