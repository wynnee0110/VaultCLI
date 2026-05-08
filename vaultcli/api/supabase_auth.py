from .supabase_db import get_db
from vaultcli.core.session import save_session


def signup(email, password):
    return get_db().signup(email, password)


def login(email, password):
    result = get_db().login(email, password)
    if result.session:
        save_session(result.session)
    return result


def refresh_session(refresh_token):
    """Attempt to refresh an expired access token using the stored refresh token."""
    try:
        result = get_db().refresh_session(refresh_token)
        if result.session:
            save_session(result.session)
            return True
    except Exception:
        pass
    return False


def logout():
    return get_db().logout()
