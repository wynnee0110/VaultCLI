import json
import os

CONFIG_DIR = os.path.expanduser("~/.vaultcli")
os.makedirs(CONFIG_DIR, exist_ok=True)
SESSION_FILE = os.path.join(CONFIG_DIR, "session.json")


def save_session(session):
    with open(SESSION_FILE, "w") as f:
        json.dump({
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": {
                "id": session.user.id
            }
        }, f)


def load_session():
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            # Return None if the file is empty or malformed
            if not data or not data.get("user"):
                return None
            return data
    except Exception:
        return None


def clear_session():
    """Delete the session file on logout."""
    try:
        os.remove(SESSION_FILE)
    except FileNotFoundError:
        pass