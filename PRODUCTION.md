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

### Render Blueprint

1. Commit and push `render.yaml`, `Dockerfile`, and `requirements-prod.txt` to `origin/main`.
2. Open `https://dashboard.render.com/blueprint/new?repo=https://github.com/Singh4Ashmeet/RAIDS_VIHAN`.
3. In the Blueprint flow, set `ADMIN_PASSWORD` and `USER_PASSWORD` to strong values.
4. Apply the Blueprint. Render will create the Docker web service and managed Postgres database.
5. After the service is live, verify:

```bash
curl https://raid-nexus.onrender.com/health
```

If Render assigns a different subdomain, update `CORS_ORIGINS` to that exact URL in the service environment.

### Docker VPS

1. Build images with `docker compose build`.
2. Start services with `docker compose up -d`.
3. Verify `curl http://localhost:8000/health`.
4. Verify the frontend loads at `http://localhost:5173`.
5. Run `python -m app.db.init_db` when bootstrapping a fresh database outside Compose.

For a public VPS, set these before building the frontend container:

```bash
VITE_API_BASE_URL=https://your-domain.example
VITE_WS_URL=wss://your-domain.example/ws/live
CORS_ORIGINS=https://your-domain.example
```

## Operations

- Monitor `/health` for database backend, timestamp, and service readiness.
- Keep PostgreSQL backups outside the application container.
- Use a process manager or orchestrator that restarts failed containers.
- Rotate `SECRET_KEY` and demo passwords before public exposure.
- Replace synthetic hospital and ambulance feeds before real emergency use.
