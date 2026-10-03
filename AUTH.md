# Optional Google sign-in + bring-your-own Gemini key

**Off by default.** If `GOOGLE_CLIENT_ID` is not set, nothing changes: no login, the server's own `GEMINI_API_KEY` is used.

## Env
| Variable | Meaning |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth Web client ID. Set it to turn auth on. |

## Endpoints / headers
- `GET /api/config` (always public) -> `{"auth_required": bool, "google_client_id": str|null}`.
- When enabled, any request that needs a **live** Gemini call must send
  - `Authorization: Bearer <Google ID token>` (verified with `google-auth`: signature, expiry, audience = `GOOGLE_CLIENT_ID`, `email_verified` true)
  - `X-Gemini-Key: <the user's own Gemini API key>`
- Applies to `POST /api/check` and `POST /api/complaint` **only on a cache miss**. Cache hits and the sample buttons stay open (no login, no key). The cache is checked first.
- No server-key fallback in auth mode: a live call uses only the caller's key, through a fresh per-request client. The local backend is not used either.

## Errors (top-level JSON `{"error": code, "message": text}`)
| Status | `error` | When |
|---|---|---|
| 401 | `login_required` | cache miss and no / blank `Authorization` |
| 401 | `invalid_token` | bad, expired, wrong-audience token, or `email_verified` false |
| 402 | `key_required` | token OK but no / blank `X-Gemini-Key` |
| 400 | `gemini_key_invalid` | Google rejected the user's key (invalid / 403) |
| 429 | `gemini_rate_limited` | the user's key hit its quota / rate limit |

A transient Gemini failure (timeout, 503) still returns 200 with code-only checks and `ai_unavailable: true` (complaints fall back to the offline template).

## Privacy note (paste into README)
> **Sign-in & your own Gemini key (optional).** When the host enables Google sign-in, new (uncached) checks need you to sign in with Google and paste your own free Gemini API key from aistudio.google.com/apikey. Your key is sent with each request, used only for that request, and is never stored, cached or logged by this server. Your Google ID token is only used to confirm who you are. The sample buttons always work without signing in. Free-tier Gemini inputs may be used by Google to improve its products, so use only fake samples for the demo.

Run with sign-in: `GOOGLE_CLIENT_ID=<id>.apps.googleusercontent.com uvicorn app:app --host 0.0.0.0 --port 8000`
