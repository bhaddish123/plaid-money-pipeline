"""Shared helpers: config loading, Plaid API calls, local file storage. Stdlib only."""
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
TOKEN_FILE = ROOT / ".plaid_token.json"
DATA_DIR = ROOT / "data"

HOSTS = {
    "production": "https://production.plaid.com",
    "sandbox": "https://sandbox.plaid.com",
}


def load_env():
    """Keys come from .env on a laptop, or from environment variables (GitHub Actions secrets)."""
    env = {k: os.environ[k] for k in ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV") if os.environ.get(k)}
    if not env.get("PLAID_CLIENT_ID") and not ENV_FILE.exists():
        sys.exit(f"Missing {ENV_FILE.name}. Copy .env.example to .env and fill in your Plaid keys.")
    for line in (ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    for key in ("PLAID_CLIENT_ID", "PLAID_SECRET"):
        if not env.get(key):
            sys.exit(f"{key} is empty in .env")
    env.setdefault("PLAID_ENV", "production")
    if env["PLAID_ENV"] not in HOSTS:
        sys.exit("PLAID_ENV must be 'production' or 'sandbox'")
    return env


def plaid(env, path, body):
    """POST to a Plaid endpoint. Raises PlaidError with Plaid's error_code on failure."""
    payload = {"client_id": env["PLAID_CLIENT_ID"], "secret": env["PLAID_SECRET"], **body}
    req = urllib.request.Request(
        HOSTS[env["PLAID_ENV"]] + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)
        except Exception:
            err = {"error_code": str(e.code), "error_message": e.reason}
        raise PlaidError(err.get("error_code", "UNKNOWN"), err.get("error_message", "")) from None


class PlaidError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


def write_private(path: Path, obj):
    """Write JSON readable only by the current user (0600)."""
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def load_token():
    if os.environ.get("PLAID_ACCESS_TOKEN"):
        return {"access_token": os.environ["PLAID_ACCESS_TOKEN"]}
    if not TOKEN_FILE.exists():
        sys.exit("No linked bank yet. Run: python link.py")
    return json.loads(TOKEN_FILE.read_text())
