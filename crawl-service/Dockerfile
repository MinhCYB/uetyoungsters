FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app \
    CAREER_COMPASS_ROOT=/app

COPY crawl-service /app/crawl-service
RUN pip install --no-cache-dir /app/crawl-service

COPY backend/shared /app/backend/shared
COPY config /app/config
COPY core /app/core

CMD ["python", "-m", "crawl_service", "status"]
