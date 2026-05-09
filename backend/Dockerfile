FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS_FILE=requirements-prod.txt
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r "$REQUIREMENTS_FILE"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
