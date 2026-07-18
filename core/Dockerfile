FROM python:3.12-slim

WORKDIR /app/core
ENV PYTHONPATH=/app

COPY core/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY core /app/core
COPY backend/shared /app/backend/shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
