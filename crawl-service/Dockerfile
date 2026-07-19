FROM python:3.12-slim

WORKDIR /app
ENV CAREER_COMPASS_ROOT=/app

COPY crawl-service/requirements.txt /app/crawl-requirements.txt
RUN pip install --no-cache-dir -r /app/crawl-requirements.txt

COPY crawl-service /app/crawl-service
RUN pip install --no-cache-dir --no-deps /app/crawl-service

COPY config /app/config

ENTRYPOINT ["python", "-m", "crawl_service"]
CMD ["status"]
