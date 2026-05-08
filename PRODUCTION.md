# Production Checklist

## Required Settings

- Set `ENVIRONMENT=production`.
- Set a strong `SECRET_KEY`.
- Set `DATABASE_URL` to PostgreSQL.
- Set explicit `CORS_ORIGINS`; do not use `*`.
- Keep `USE_LLM=false` unless an approved local or paid provider is configured.
- Disable heavy NLP models on small instances with `ENABLE_NLP_TRIAGE=false` and `ENABLE_TRANSLATION=false`.

## Security

- All secrets are read from environment variables.
- CORS is restricted from `CORS_ORIGINS` in production.
- Pydantic validates request bodies on incident, patient, dispatch, auth, driver, and scenario flows.
- Logs avoid patient PII and redact obvious name, phone, and address fields where structured sanitizers are used.
- Client errors use stable JSON envelopes and production uncaught errors return a generic message.
- `/api/dispatch` is rate limited with SlowAPI.
- No `eval()`, `exec()`, or `shell=True` is used for user-controlled dispatch paths.

## Deployment

1. Build images with `docker compose build`.
2. Start services with `docker compose up -d`.
3. Verify `curl http://localhost:8000/health`.
4. Verify the frontend loads at `http://localhost:5173`.
5. Run `python -m app.db.init_db` when bootstrapping a fresh database outside Compose.

## Operations

- Monitor `/health` for database backend, timestamp, and service readiness.
- Keep PostgreSQL backups outside the application container.
- Use a process manager or orchestrator that restarts failed containers.
- Rotate `SECRET_KEY` and demo passwords before public exposure.
- Replace synthetic hospital and ambulance feeds before real emergency use.
