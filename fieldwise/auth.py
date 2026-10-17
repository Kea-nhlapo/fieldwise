"""Officer PIN for anything that changes records or shows farmer reports.

Set FIELDWISE_OFFICER_PIN to turn it on. Without it the app runs open, for tests and local
development, and logs a warning. Signing in sets an HttpOnly session cookie for 12 hours.
The USSD callback stays open: Africa's Talking has to reach it without a session.
"""
import hmac
import logging
import os
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
COOKIE = 'fieldwise_session'
SESSION_SECONDS = 12 * 3600
MAX_FAILURES, LOCKOUT_SECONDS = 5, 300

# Reads that hold no farmer reports or answers.
OPEN_READS = ('/api/health', '/api/session', '/api/impact', '/api/simulation', '/api/disease/reference', '/api/felix/map')


def needs_officer(method, path):
    if path == '/ussd' or path == '/api/session':
        return False
    if not path.startswith('/api/'):
        return False
    if method in ('GET', 'HEAD'):
        return not path.startswith(OPEN_READS)
    return True


def register_auth(app, pin):
    sessions = {}        # token -> expiry
    failures = {}        # client -> recent failure times
    app.state.auth_enabled = bool(pin)
    if not pin:
        logger.warning('FIELDWISE_OFFICER_PIN is not set: records and exports are open to anyone who can reach the server.')

    def signed_in(request):
        token = request.cookies.get(COOKIE)
        expiry = sessions.get(token) if token else None
        if expiry and expiry < time.time():
            sessions.pop(token, None)
            return False
        return bool(expiry)

    # Registered after the offline replay middleware, so it wraps it: a request without a session is
    # turned away before the replay guard can remember the refusal under its idempotency key.
    @app.middleware('http')
    async def require_officer(request: Request, call_next):
        if pin and needs_officer(request.method, request.url.path) and not signed_in(request):
            return JSONResponse({'detail': 'Officer PIN required.', 'auth': 'required'}, status_code=401)
        return await call_next(request)

    @app.get('/api/session')
    def session(request: Request):
        return {'auth_enabled': bool(pin), 'signed_in': bool(pin) and signed_in(request)}

    @app.post('/api/session')
    async def sign_in(request: Request):
        if not pin:
            return {'auth_enabled': False, 'signed_in': False}
        client = request.client.host if request.client else 'unknown'
        now = time.time()
        recent = [t for t in failures.get(client, []) if now - t < LOCKOUT_SECONDS]
        if len(recent) >= MAX_FAILURES:
            return JSONResponse({'detail': 'Too many wrong PINs. Wait five minutes and try again.'}, status_code=429)
        try:
            entered = str((await request.json()).get('pin', ''))
        except Exception:
            entered = ''
        if not hmac.compare_digest(entered.encode(), pin.encode()):
            failures[client] = recent + [now]
            return JSONResponse({'detail': 'That PIN is not right.'}, status_code=401)
        failures.pop(client, None)
        token = secrets.token_urlsafe(32)
        sessions[token] = now + SESSION_SECONDS
        response = JSONResponse({'auth_enabled': True, 'signed_in': True})
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite='strict')
        return response

    @app.delete('/api/session')
    def sign_out(request: Request):
        sessions.pop(request.cookies.get(COOKIE, ''), None)
        response = JSONResponse({'signed_in': False})
        response.delete_cookie(COOKIE)
        return response


def officer_pin(explicit=None):
    return explicit if explicit is not None else os.environ.get('FIELDWISE_OFFICER_PIN', '')
