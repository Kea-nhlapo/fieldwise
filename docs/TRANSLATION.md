# Farmer-facing text for translation

Every string a farmer can see on their phone. Send this file to a Chichewa translator and paste the translations into the right-hand column. Fieldwise does not machine-translate farmer messages.

USSD screens must fit **182 characters**, including the farm name and the numbered options. `tests/test_ussd.py` checks the English versions; run it again after adding translations.

## USSD check-in (`fieldwise/ussd.py`)

| Screen | English | Chichewa |
|---|---|---|
| Welcome | Fieldwise crop check-in. Enter your farm number (for example 14) | |
| Consent | Fieldwise helps your extension officer plan visits. We keep your farm number and answers, not your phone number. You can say no. 1 Agree 2 No thanks | |
| Declined | Thank you. Nothing was saved. Saying no does not affect support for your farm. | |
| Question 1, dry weather | Are plants wilting during the day? 1. Yes 2. No 3. Not sure | |
| Question 1, heavy rain on clay | Is there standing water in your field? 1. Yes 2. No 3. Not sure | |
| Question 1, no signal | Have you noticed a new crop problem? 1. Yes 2. No 3. Not sure | |
| Question 2 | Is more than one part of the field affected? 1. One area 2. Several areas 3. Not sure | |
| Question 3 | When did you first see this? 1. Today 2. Before today 3. Not sure | |
| Saved | Thank you. Your extension officer has your answers. | |
| Unknown farm | Farm number not found. Please check the number from your extension officer and dial again. | |
| Bad input | Please answer with 1, 2 or 3. Dial again to restart. | |

## SMS drafts, South Africa workspace (`fieldwise/app.py`)

| Message | English |
|---|---|
| Irrigation | Fieldwise: Is irrigation working on your maize plot at {farm}? Reply 1 yes, 2 no, 3 no irrigation. |
| Leaf spots | Fieldwise: Have you noticed unusual leaf spots on maize at {farm}? Reply 1 symptoms noticed, 2 none noticed, 3 unsure. Officer review for {disease}; this question does not diagnose disease. |

South African farmers may need these in isiZulu, Sesotho or another local language. The language depends on the district.
