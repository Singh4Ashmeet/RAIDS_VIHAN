# Deployment — RAID Nexus

## Recommended Target

RAID Nexus is best deployed as a single Docker-backed Render web service for the current prototype. The FastAPI backend serves the built React frontend from `frontend/dist`, so a separate static frontend service is optional rather than required.

## Required Provider

Use Render for the first deployment. The project depends on FastAPI, WebSockets, Torch, Transformers, local model downloads, and background CPU work. Those requirements are a better fit for Render than static-only hosting.

## Required Secrets

Set these environment variables in Render:

| Variable | Required | Notes |
|---|---:|---|
| `SECRET_KEY` | Yes | Random production JWT secret. The blueprint can generate it. |
| `ADMIN_USERNAME` | Yes | Default can be `admin`. |
| `ADMIN_PASSWORD` | Yes | Choose a strong password. Do not commit it. |
| `USER_USERNAME` | Yes | Default can be `user`. |
| `USER_PASSWORD` | Yes | Choose a strong password. Do not commit it. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Default `480`. |
| `ALGORITHM` | Yes | Default `HS256`. |
| `RAID_LIGHTWEIGHT_TRIAGE` | Recommended on free tier | Set to `1` for Render free tier; omit or set `0` for full NLP on larger instances. |
| `RAID_DISABLE_SIMULATION` | Recommended on free tier | Set to `1` for hosted demos to prevent background simulation from consuming routing/API resources. |

## Resource Notes

The NLP classifier and offline translation models are large. Use at least a Render Starter instance for practical testing. The Blueprint includes a persistent disk at `/opt/render/project/.cache` so Hugging Face model files can be cached after first download.

Render's free web-service instances have a 512 MB memory ceiling. For free deployment, set `RAID_LIGHTWEIGHT_TRIAGE=1`. This keeps the application online by using language detection plus keyword/Hinglish safety triage instead of loading Torch/Transformers models at startup. Full NLP triage requires a larger instance.

Hosted demo deployments should also set `RAID_DISABLE_SIMULATION=1`. This disables only the background auto-simulation loop that periodically generates incidents and routing calls. Manual SOS submission, login, dashboards, and admin APIs remain available.

## Deployment Flow

1. Push the repository to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Render reads `render.yaml`, builds the Docker image, and starts the service.
4. Add `ADMIN_PASSWORD` and `USER_PASSWORD` when prompted.
5. Open the service URL and verify `/health`, `/login`, and `/user/sos`.

## Expected First Boot

First use of NLP triage may download Hugging Face model files. The service may be slow during the first model load. Later requests should use the cached files on the mounted disk.
