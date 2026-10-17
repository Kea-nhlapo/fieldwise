"""Disposable server for browser checks. Never uses the saved demo database.

    .venv/Scripts/python.exe scripts/serve-test.py --port 8769 --pin 2468

TEST ONLY: a request carrying `X-Test-Slow-Body: <seconds>` gets its response headers at once and
its body that many seconds later. The browser checks use this to sign out while a record's body is
still downloading. The live app (fieldwise.app:app) never includes this wrapper.
"""
import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fieldwise.app import create_app  # noqa: E402


def slow_body(app):
    async def wrapped(scope, receive, send):
        delay = 0.0
        if scope['type'] == 'http':
            for name, value in scope.get('headers', []):
                if name == b'x-test-slow-body':
                    delay = min(float(value or 0), 30.0)
        if not delay:
            return await app(scope, receive, send)
        held = {'done': False}

        async def delayed_send(message):
            if message['type'] == 'http.response.body' and not held['done']:
                held['done'] = True
                await asyncio.sleep(delay)
            await send(message)
        return await app(scope, receive, delayed_send)
    return wrapped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--pin', default='', help='officer PIN; empty runs the app open')
    parser.add_argument('--ussd-key', default='')
    args = parser.parse_args()
    db = Path(tempfile.mkdtemp(prefix='fieldwise-check-')) / 'browser.db'
    app = create_app(db, officer_pin_value=args.pin, ussd_key_value=args.ussd_key)
    uvicorn.run(slow_body(app), host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
