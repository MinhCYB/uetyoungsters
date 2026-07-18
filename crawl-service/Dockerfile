FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt /tmp/data-requirements.txt
COPY crawl-service/requirements.txt /tmp/service-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/data-requirements.txt \
    -r /tmp/service-requirements.txt

COPY backend /app/backend
COPY config /app/config
COPY scripts /app/scripts
COPY run_pipeline.py /app/run_pipeline.py
COPY crawl-service/main.py /app/crawl-service/main.py

CMD ["python", "/app/crawl-service/main.py"]
