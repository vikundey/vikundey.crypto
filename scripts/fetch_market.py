import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


API_KEY = os.environ.get("TWELVE_DATA_API_KEY")

if not API_KEY:
    raise RuntimeError("TWELVE_DATA_API_KEY is missing")


SYMBOLS = {
    "EURUSD": "EUR/USD",
    "XAUUSD": "XAU/USD",
    "BTC": "BTC/USD",
}


def fetch_price(symbol):
    params = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "apikey": API_KEY,
        }
    )

    url = f"https://api.twelvedata.com/price?{params}"

    with urllib.request.urlopen(url, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    if "price" not in data:
        raise RuntimeError(
            f"Could not fetch {symbol}: {data}"
        )

    return float(data["price"])


def main():
    assets = {}

    for display_name, api_symbol in SYMBOLS.items():
        try:
            price = fetch_price(api_symbol)

            assets[display_name] = {
                "symbol": api_symbol,
                "price": price,
                "status": "ok",
            }

            print(
                f"{display_name}: {price}"
            )

        except Exception as error:
            assets[display_name] = {
                "symbol": api_symbol,
                "price": None,
                "status": "error",
                "error": str(error),
            }

            print(
                f"ERROR {display_name}: {error}"
            )

    now = datetime.now(
        ZoneInfo("Europe/Kyiv")
    )

    result = {
        "updated_at": now.isoformat(),
        "timezone": "Europe/Kyiv",
        "assets": assets,
    }

    output_path = Path("data/live_market.json")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved to {output_path}"
    )


if __name__ == "__main__":
    main()
