import os
from supabase import create_client
from dotenv import load_dotenv
from session import save_session

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(url, key)


def signup(email, password):
    res = supabase.auth.sign_up({
        "email": email,
        "password": password
    })
    return res


def login(email, password):
    res = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    save_session(res.session)   # FIX: was never called before
    return res


def refresh_session(refresh_token):
    """Attempt to refresh an expired access token using the stored refresh token."""
    try:
        res = supabase.auth.refresh_session(refresh_token)
        if res.session:
            save_session(res.session)
            return True
    except Exception:
        pass
    return False


def logout():
    supabase.auth.sign_out()