"""USSD check-in in the Africa's Talking callback format.

Africa's Talking POSTs form fields sessionId, serviceCode, phoneNumber, networkCode and
text, where text holds every input so far joined by '*'. The reply is plain text that
starts with 'CON ' (show a menu and wait) or 'END ' (close the session).

The phone number is never stored or logged: the farmer identifies the farm by number,
and the answers go through the same consent-checked check-in as the web flow.
"""
import hmac
import logging
import os
import re
from urllib.parse import parse_qs

from fastapi import HTTPException, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)
KEY_HEADER = 'X-Fieldwise-Ussd-Key'
_KEY_IN_URL = re.compile(r'([?&]key=)[^&\s"]*')


class RedactUssdKey(logging.Filter):
    """Access logs record full URLs. Providers that can only call a plain URL send the key as ?key=,
    so replace its value before the line is written. (A proxy in front of the server needs the same.)"""

    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def redact(text):
    """Replace the value of any key= query parameter, keeping the parameter name."""
    return _KEY_IN_URL.sub(lambda m: m.group(1) + '[REDACTED]', text)


def redact_access_logs():
    access = logging.getLogger('uvicorn.access')
    if not any(isinstance(f, RedactUssdKey) for f in access.filters):
        access.addFilter(RedactUssdKey())
MAX_TEXT = 64   # a full check-in is under 20 characters

FOLLOW_UPS = ['Is more than one part of the field affected?', 'When did you first see this?']
OPTIONS = [['Yes', 'No', 'Not sure'], ['One area', 'Several areas', 'Not sure'], ['Today', 'Before today', 'Not sure']]
NOTICE = ('Fieldwise helps your extension officer plan visits. We keep your farm number and answers, '
          'not your phone number. You can say no.\n1 Agree\n2 No thanks')


def branch_complete(answers):
    """Same branching as the web check-in: 'No' ends after one answer, 'One area' after two, else three."""
    if not answers: return False
    expected = 1 if answers[0] == 2 else (2 if len(answers) > 1 and answers[1] == 1 else 3)
    return len(answers) == expected


def menu(question, options):
    return 'CON ' + question + '\n' + '\n'.join(f'{i}. {label}' for i, label in enumerate(options, 1))


def register_ussd(app, lookup_farm, submit_check_in, key=None, service_code=None):
    """lookup_farm(fid) -> (farm, question, survey_id) or None; submit_check_in(fid, answers, survey_id) -> None.

    key: the provider callback is registered as /ussd?key=<key>. Without a key the callback is switched off,
    so nobody can submit answers to an unconfigured server. service_code, if set, must match the request.
    """
    key = key if key is not None else os.environ.get('FIELDWISE_USSD_KEY', '')
    service_code = service_code if service_code is not None else os.environ.get('FIELDWISE_USSD_CODE', '')
    if not key:
        logger.warning('FIELDWISE_USSD_KEY is not set: the /ussd provider callback is switched off.')
    redact_access_logs()

    async def form(request):
        return {k: v[0] for k, v in parse_qs((await request.body()).decode('utf-8', 'replace')).items()}

    def safely(text):
        # A USSD gateway shows whatever we return, so never answer with an HTTP error.
        try:
            return respond(text)
        except Exception:
            logger.exception('USSD request failed')
            return 'END Sorry, something went wrong. Please dial again.'

    @app.post('/ussd', response_class=PlainTextResponse, tags=['USSD (Africa’s Talking format)'])
    async def ussd(request: Request):
        if not key:
            return PlainTextResponse('USSD callback is switched off. Set FIELDWISE_USSD_KEY.', status_code=404)
        # Prefer the header (never in URLs or access logs); ?key= is accepted for providers that only call a URL.
        supplied = request.headers.get(KEY_HEADER) or request.query_params.get('key', '')
        if not hmac.compare_digest(supplied.encode(), key.encode()):
            return PlainTextResponse('Not a registered USSD gateway.', status_code=403)
        fields = await form(request)
        if service_code and fields.get('serviceCode', '') != service_code:
            return 'END This service code is not registered for Fieldwise.'
        return safely(fields.get('text', ''))

    @app.post('/api/ussd/simulate', response_class=PlainTextResponse, tags=['USSD (Africa’s Talking format)'])
    async def ussd_simulator(request: Request):
        # Same menus for the in-app phone simulator. Under /api/, so it needs an officer session when a PIN is set.
        return safely((await form(request)).get('text', ''))

    def respond(text):
        if len(text) > MAX_TEXT:
            return 'END Too many answers. Please dial again to restart.'
        steps = [s.strip() for s in text.split('*')] if text else []
        if not steps:
            return 'CON Fieldwise crop check-in\nEnter your farm number (for example 14)'
        number = steps[0].lstrip('Ff').lstrip('0')
        found = lookup_farm(f'F{int(number):03d}') if number.isdigit() else None
        if not found:
            return 'END Farm number not found. Please check the number from your extension officer and dial again.'
        farm, question, survey_id = found
        if len(steps) == 1:
            return f"CON {farm['name']}\n{NOTICE}"
        if steps[1] != '1':
            return 'END Thank you. Nothing was saved. Saying no does not affect support for your farm.'
        raw = steps[2:]
        if any(a not in ('1', '2', '3') for a in raw):
            return 'END Please answer with 1, 2 or 3. Dial again to restart.'
        answers = [int(a) for a in raw]
        if not branch_complete(answers):
            if len(answers) >= len(OPTIONS) or past_branch_end(answers):
                return 'END Too many answers. Please dial again to restart.'
            questions = [question] + FOLLOW_UPS
            return menu(questions[len(answers)], OPTIONS[len(answers)])
        try:
            submit_check_in(farm['id'], answers, survey_id)
        except HTTPException as error:
            return f'END Could not save: {str(error.detail)[:120]}'
        return 'END Thank you. Your extension officer has your answers.'

    return ussd


def past_branch_end(answers):
    """True when the answers already went beyond where this branch should have ended."""
    return any(branch_complete(answers[:n]) for n in range(1, len(answers)))
