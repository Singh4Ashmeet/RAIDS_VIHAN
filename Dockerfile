FROM node:22-slim AS frontend

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

ARG REQUIREMENTS_FILE=requirements-prod.txt
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r "$REQUIREMENTS_FILE"

COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

EXPOSE 8000 10000

CMD ["sh", "-c", "if [ \"$ENVIRONMENT\" = \"production\" ]; then cd backend && alembic upgrade head && cd /app && export RAID_SKIP_STARTUP_MIGRATIONS=1; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
