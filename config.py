"""Bot configuration - .env se load hota hai."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
try:
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

BASE_DIR = Path(__file__).resolve().parent
# Railway Volume lagane par DATA_DIR=/data set karo taaki data.json redeploy me na ude
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_FILE = DATA_DIR / "data.json"
BACKUP_FILE = DATA_DIR / "data.json.bak"

POLL_OPEN_SECONDS = 20
TIMEOUT_GRACE = 8  # poll expire ke baad kitna wait karke auto-advance
HISTORY_LIMIT = 10
LEADERBOARD_LIMIT = 10
REVIEW_PAGE_SIZE = 5
PAGE_SIZE = 10

