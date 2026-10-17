"""Disposable local server for UI checks; never uses the saved demo database."""
import sys
import tempfile
from pathlib import Path
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fieldwise.app import create_app

with tempfile.TemporaryDirectory(prefix='fieldwise-disease-browser-') as directory:
    uvicorn.run(create_app(Path(directory) / 'browser.db'), host='127.0.0.1', port=8766)
