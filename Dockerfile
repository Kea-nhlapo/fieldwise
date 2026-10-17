# Fieldwise server image.
# Built and smoke-tested 2026-10-17: all pages, APIs and the USSD flow returned 200 inside the container.
# Build: docker build -t fieldwise .
# Run:   docker run -p 8765:8765 -v fieldwise-data:/app/data -e FIELDWISE_OFFICER_PIN=<choose one> fieldwise
# Without FIELDWISE_OFFICER_PIN the app runs open and logs a warning.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fieldwise ./fieldwise
COPY static ./static
COPY examples ./examples

# SQLite lives on a volume so farm records survive container restarts.
VOLUME /app/data
ENV FIELDWISE_RETENTION_DAYS=180
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "fieldwise.app:app", "--host", "0.0.0.0", "--port", "8765"]
