"""Officer PIN for anything that changes records or shows farmer reports.

Set FIELDWISE_OFFICER_PIN to turn it on. Without it the app runs open, for tests and local
development, and logs a warning.

A signed-in request needs two things:
  * the HttpOnly session cookie set at sign-in, and
  * the matching X-Officer-Token header, which pages keep on the device and send with every
    request (static/offline.js).
Signing out deletes the device's token straight away, even offline, so a leftover cookie is useless
from every entry point (another page, /docs, a typed URL) until the server session also ends. The
header also means a request forged by another site cannot act as the officer.

The USSD provider callback is not an officer route; it is guarded separately in fieldwise/ussd.py.
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
HEADER = 'X-Officer-Token'
SESSION_SECONDS = 12 * 3600
MAX_FAILURES, LOCKOUT_SECONDS = 5, 300

# Reads that hold no farmer reports or answers. Mirrored in static/sw.js and static/offline.js.
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
    sessions = {}        # cookie value -> {'expiry': ..., 'officer_token': ...}
    failures = {}        # client -> recent failure times
    app.state.auth_enabled = bool(pin)
    if not pin:
        logger.warning('FIELDWISE_OFFICER_PIN is not set: records and exports are open to anyone who can reach the server.')

    def session_for(request):
        cookie = request.cookies.get(COOKIE)
        session = sessions.get(cookie) if cookie else None
        if session and session['expiry'] < time.time():
            sessions.pop(cookie, None)
            return None
        return session

    def signed_in(request):
        session = session_for(request)
        header = request.headers.get(HEADER, '')
        return bool(session) and hmac.compare_digest(header.encode(), session['officer_token'].encode())

    # Registered after the offline replay middleware, so it wraps it: a request without a session is
    # turned away before the replay guard can remember the refusal under its idempotency key.
    @app.middleware('http')
    async def require_officer(request: Request, call_next):
        record = needs_officer(request.method, request.url.path)
        if pin and record and not signed_in(request):
            return JSONResponse({'detail': 'Officer PIN required.', 'auth': 'required'}, status_code=401)
        response = await call_next(request)
        if record:
            # Farmer records stay out of the browser's HTTP cache; the offline copy is managed (and
            # deleted on sign-out) by the service worker.
            response.headers['Cache-Control'] = 'no-store'
        return response

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
        cookie, officer_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        sessions[cookie] = {'expiry': now + SESSION_SECONDS, 'officer_token': officer_token}
        response = JSONResponse({'auth_enabled': True, 'signed_in': True, 'officer_token': officer_token})
        response.set_cookie(COOKIE, cookie, max_age=SESSION_SECONDS, httponly=True, samesite='strict')
        return response

    @app.delete('/api/session')
    def sign_out(request: Request):
        # Needs only the cookie: signing out must always be possible.
        sessions.pop(request.cookies.get(COOKIE, ''), None)
        response = JSONResponse({'signed_in': False})
        response.delete_cookie(COOKIE)
        return response


def officer_pin(explicit=None):
    return explicit if explicit is not None else os.environ.get('FIELDWISE_OFFICER_PIN', '')
