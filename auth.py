"""Optional Google sign-in + bring-your-own Gemini key. OFF unless GOOGLE_CLIENT_ID is set (see AUTH.md).
Neither the ID token nor the user's Gemini key is ever logged, cached or stored."""
import os


class AuthError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def client_id():
    return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip() or None


def enabled():
    return client_id() is not None


def _google_verify(token):
    from google.auth.transport import requests as greq
    from google.oauth2 import id_token
    return id_token.verify_oauth2_token(token, greq.Request(), client_id())


verify_google_token = _google_verify  # injectable: tests replace this (token -> claims dict, or raise)


def require_user_key(headers):
    """Call only when a LIVE Gemini call is needed (after the cache missed). Returns the caller's Gemini key.
    401 login_required (no/blank Authorization) -> 401 invalid_token -> 402 key_required."""
    raw = (headers.get("authorization") or "").strip()
    if not raw:
        raise AuthError(401, "login_required", "Please sign in with Google to run a new check. Sample buttons work without signing in.")
    scheme, _, token = raw.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthError(401, "invalid_token", "Your sign-in is invalid or has expired. Please sign in again.")
    try:
        claims = verify_google_token(token)
        ok = isinstance(claims, dict) and claims.get("email_verified") is True
    except Exception:
        ok = False
    if not ok:
        raise AuthError(401, "invalid_token", "Your sign-in is invalid or has expired. Please sign in again.")
    key = (headers.get("x-gemini-key") or "").strip()
    if not key:
        raise AuthError(402, "key_required", "Add your own free Gemini API key (aistudio.google.com/apikey) to run new checks.")
    return key
