import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

RESEARCH_ROLES = {"researcher", "admin"}
CONTENT_ROLES = {"facilitator", "researcher", "admin"}
QUIZ_ROUND_SIZE = 7
