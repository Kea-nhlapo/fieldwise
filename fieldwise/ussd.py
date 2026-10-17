"""USSD check-in in the Africa's Talking callback format.

Africa's Talking POSTs form fields sessionId, serviceCode, phoneNumber, networkCode and
text, where text holds every input so far joined by '*'. The reply is plain text that
starts with 'CON ' (show a menu and wait) or 'END ' (close the session).

The phone number is never stored or logged: the farmer identifies the farm by number,
and the answers go through the same consent-checked check-in as the web flow.
"""
from urllib.parse import parse_qs

from fastapi import HTTPException, Request
from fastapi.responses import PlainTextResponse

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


def register_ussd(app, lookup_farm, submit_check_in):
    """lookup_farm(fid) -> (farm, question, survey_id) or None; submit_check_in(fid, answers, survey_id) -> None."""

    @app.post('/ussd', response_class=PlainTextResponse, tags=['USSD (Africa’s Talking format)'])
    async def ussd(request: Request):
        fields = {k: v[0] for k, v in parse_qs((await request.body()).decode('utf-8', 'replace')).items()}
        steps = [s.strip() for s in fields.get('text', '').split('*')] if fields.get('text') else []
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
            questions = [question] + FOLLOW_UPS
            return menu(questions[len(answers)], OPTIONS[len(answers)])
        try:
            submit_check_in(farm['id'], answers, survey_id)
        except HTTPException as error:
            return f'END Could not save: {error.detail}'
        return 'END Thank you. Your extension officer has your answers.'

    return ussd
