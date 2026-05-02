import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "merged_output")
MAX_UPLOAD_SIZE_MB = 50
MODEL = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1M]")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
# Disable SSL verification and proxy for corporate networks
HTTP_VERIFY_SSL = os.environ.get("HTTP_VERIFY_SSL", "false").lower() == "true"
HTTP_TRUST_ENV = os.environ.get("HTTP_TRUST_ENV", "false").lower() == "true"

os.makedirs(UPLOAD_DIR, exist_ok=True)
