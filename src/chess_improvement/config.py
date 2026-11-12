"""Project-wide settings: paths, username, HTTP etiquette."""
from pathlib import Path

USERNAME = "matthewsharpe99"  # chess.com API usernames are lower-case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # one JSON file per monthly archive
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
GAMES_TABLE = PROCESSED_DIR / "games.parquet"

# chess.com asks automated clients to identify themselves and to avoid parallel requests.
USER_AGENT = "chess-improvement-analysis/0.1 (personal game-history analysis script)"
REQUEST_SLEEP_S = 1.0
