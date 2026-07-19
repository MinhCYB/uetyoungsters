FROM python:3.12-slim
WORKDIR /app
COPY backend-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend-api/ .
COPY tests/fixtures/ /app/tests/fixtures/
COPY crawl-service/data/taxonomy.json /app/data/taxonomy.json
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
