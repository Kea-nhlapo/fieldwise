@echo off
cd /d "%~dp0"
rem Demo PIN for officer sign-in. Set FIELDWISE_OFFICER_PIN yourself before a real pilot.
if not defined FIELDWISE_OFFICER_PIN set FIELDWISE_OFFICER_PIN=2468
echo Fieldwise: http://127.0.0.1:8765
echo Officer PIN: %FIELDWISE_OFFICER_PIN%
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn fieldwise.app:app --host 127.0.0.1 --port 8765
pause
