"""Phase 1a: download monthly game archives from the public chess.com API.

Each monthly archive is cached as data/raw/YYYY-MM.json. Past months never change, so
they are fetched once. The current month is re-fetched on each run because new games
keep arriving.

Run:  uv run python -m chess_improvement.download
"""
from __future__ import annotations

import datetime as dt
import json
import time

import requests

from .config import RAW_DIR, REQUEST_SLEEP_S, USER_AGENT, USERNAME

ARCHIVES_URL = f"https://api.chess.com/pub/player/{USERNAME}/games/archives"


def _get(session: requests.Session, url: str, retries: int = 3) -> dict:
    """GET a JSON endpoint, backing off on HTTP 429 (rate limit) and 5xx responses."""
    for attempt in range(retries):
        resp = session.get(url, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    raise RuntimeError(f"Failed to fetch {url}")


def download_all(force: bool = False) -> list[str]:
    """Fetch every monthly archive that isn't cached yet, one request at a time.

    Args:
        force: re-download every month, even ones already cached.

    Returns:
        The archive URLs that were downloaded on this run.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    archive_urls = _get(session, ARCHIVES_URL)["archives"]
    current_month = dt.date.today().strftime("%Y/%m")
    fetched = []
    for url in archive_urls:
        year_month = "/".join(url.rstrip("/").split("/")[-2:])  # e.g. "2023/04"
        path = RAW_DIR / f"{year_month.replace('/', '-')}.json"
        if path.exists() and not force and year_month != current_month:
            continue
        time.sleep(REQUEST_SLEEP_S)
        data = _get(session, url)
        path.write_text(json.dumps(data))
        fetched.append(url)
        print(f"fetched {year_month}: {len(data.get('games', []))} games")
    print(f"{len(archive_urls)} archives listed, {len(fetched)} downloaded this run")
    return fetched


if __name__ == "__main__":
    download_all()
