import os
import secrets
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"

try:
    from dotenv import load_dotenv
    load_dotenv(APP_DIR / ".env")
except ImportError:
    pass

SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
QUIZ_ROUND_SIZE = int(os.environ.get("QUIZ_ROUND_SIZE", "7"))

RESEARCH_ROLES = {"researcher", "admin"}
CONTENT_ROLES = {"facilitator", "researcher", "admin"}
