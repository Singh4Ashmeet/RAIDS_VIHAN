"""FastAPI application entrypoint for RAID Nexus Day 1."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware


from api.ambulances import router as ambulances_router
from api.auth import get_current_admin, router as auth_router
from api.dispatch import router as dispatch_router
from api.hospitals import router as hospitals_router
from api.incidents import router as incidents_router
from api.overrides import router as overrides_router
from api.patients import router as patients_router
from api.system import router as system_router
from api.websocket import router as websocket_router
from core.config import DATA_DIR, isoformat_utc, settings
from repositories.database import (
    IS_POSTGRES,
    close_connection,
    count_rows,
    database_backend_label,
    initialize_database,
    load_seed_data,
)
from repositories.ambulance_repo import AmbulanceRepository
from repositories.hospital_repo import HospitalRepository
from repositories.incident_repo import IncidentRepository
from repositories.patient_repo import PatientRepository
from core.security import limiter
from schemas.scenario import DispatchRequest as BaseDispatchRequest
from services.anomaly_detector import get_recent_anomalies, get_total_detected
from services.demand_predictor import CITY_BOUNDING_BOXES, build_density_grid, predict_demand, recommend_preposition
from services.dispatch import select_dispatch
from services.dispatch_service import full_dispatch_pipeline, save_dispatch_bg
from services.nlp_triage import triage_incident
from services.offline_translator import get_translation_status
from simulation.engine import SimulationEngine
from core.response import error, fallback, success, unwrap_envelope
from alembic import command
from alembic.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
CPU_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="raid_cpu",
)
FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='#101828'/>"
    "<path d='M18 18h28v8H32v20h-8V26H18z' fill='#22c55e'/>"
    "<circle cx='46' cy='46' r='6' fill='#38bdf8'/>"
    "</svg>"
)
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
FRONTEND_RESERVED_PATHS = {"api", "docs", "health", "openapi.json", "redoc", "ws"}
BENCHMARK_RESULTS_FILE = DATA_DIR / "benchmark_results.json"
LITERATURE_COMPARISON_FILE = DATA_DIR / "literature_comparison.json"
_BENCHMARK_CACHE: dict[str, object] = {}
LIGHTWEIGHT_TRIAGE = (not settings.ENABLE_NLP_TRIAGE) or os.getenv("RAID_LIGHTWEIGHT_TRIAGE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DISABLE_SIMULATION = settings.RAID_DISABLE_SIMULATION or os.getenv("RAID_DISABLE_SIMULATION", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _ensure_cpu_executor() -> ThreadPoolExecutor:
    """Return a live CPU executor, recreating it when tests restart the app."""

    global CPU_EXECUTOR
    if getattr(CPU_EXECUTOR, "_shutdown", False):
        CPU_EXECUTOR = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="raid_cpu",
        )
    return CPU_EXECUTOR


def _load_json_payload(path: Path) -> dict[str, Any]:
    """Read and parse a UTF-8 JSON file from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


class TimingMiddleware(BaseHTTPMiddleware):
    """Attach request timing headers and structured API timing logs."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        if request.url.path.startswith("/api/"):
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response


class DispatchRequest(BaseDispatchRequest):
    """Manual dispatch trigger request."""

    patient_id: str | None = None


def _format_api_message(detail: Any, fallback: str = "Request failed") -> str:
    """Return a compact string message for arbitrary FastAPI error details."""

    if detail is None:
        return fallback
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = [_format_api_message(item, "") for item in detail]
        return "; ".join(message for message in messages if message) or fallback
    if isinstance(detail, dict):
        if "detail" in detail:
            return _format_api_message(detail["detail"], fallback)
        message = detail.get("message") or detail.get("msg")
        if message:
            location = detail.get("loc")
            if isinstance(location, list):
                path = ".".join(str(part) for part in location if part != "body")
                return f"{path}: {message}" if path else str(message)
            return str(message)
        try:
            return json.dumps(detail, default=str)
        except TypeError:
            return fallback
    return str(detail)


def _parse_cors_origins(value: str) -> list[str]:
    """Parse CORS origins from comma-separated or JSON-list configuration."""

    raw_value = value.strip()
    if not raw_value:
        return []
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(origin).strip() for origin in parsed if str(origin).strip()]
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def _cors_origins() -> list[str]:
    """Return allowed CORS origins, honoring comma-separated env overrides."""

    return _parse_cors_origins(os.getenv("CORS_ORIGINS") or settings.CORS_ORIGINS)


def _cors_origin_regex() -> str | None:
    """Keep the development regex only when origins are not explicitly set."""

    if os.getenv("CORS_ORIGINS"):
        return None
    return settings.CORS_ORIGIN_REGEX or None


async def health() -> dict[str, Any]:
    """Return a simple liveness payload."""

    translation_status = await get_translation_status()
    return {
        "status": "ok",
        "service": "RAID Nexus",
        "version": "1.0.0",
        "timestamp": isoformat_utc(),
        "services": {
            "translation": "ok" if translation_status["model_count"] > 0 else "idle (loads on first use)",
        },
        "performance": {
            "cpu_executor_workers": 4,
            "active_threads": threading.active_count(),
            "event_loop_running": asyncio.get_running_loop().is_running(),
            "database_type": database_backend_label(),
            "database_note": "Uses DATABASE_URL for PostgreSQL; falls back to local SQLite when unset",
        },
    }


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return friendly JSON responses for throttled endpoints."""

    if request.url.path == "/api/incidents":
        message = (
            "Too many requests. Emergency services have been notified. "
            "If this is a real emergency please call 112."
        )
    else:
        message = _format_api_message(getattr(exc, "detail", None), "Rate limit exceeded")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error(message, code=status.HTTP_429_TOO_MANY_REQUESTS),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a stable envelope for uncaught errors."""

    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "data": None},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return HTTP errors in the standard envelope."""

    _ = request
    return JSONResponse(
        status_code=exc.status_code,
        content=error(_format_api_message(exc.detail, "HTTP error"), code=exc.status_code),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return request validation errors in the standard envelope."""

    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error(
            _format_api_message(exc.errors(), "Validation error"),
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    )


async def benchmark_results() -> JSONResponse:
    """Return cached benchmark results from disk when available."""

    cached_payload = _BENCHMARK_CACHE.get("data")
    if cached_payload is not None:
        return JSONResponse(content=success(cached_payload), media_type="application/json")

    if not BENCHMARK_RESULTS_FILE.is_file():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error("Benchmark not run yet", code=status.HTTP_404_NOT_FOUND),
            media_type="application/json",
        )

    payload = await asyncio.to_thread(_load_json_payload, BENCHMARK_RESULTS_FILE)
    _BENCHMARK_CACHE["data"] = payload
    return JSONResponse(content=success(payload), media_type="application/json")


async def fairness_results(_admin: Any = Depends(get_current_admin)) -> JSONResponse:
    """Return the latest benchmark fairness report."""

    _ = _admin
    if not BENCHMARK_RESULTS_FILE.is_file():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error("Run benchmark first", code=status.HTTP_404_NOT_FOUND),
            media_type="application/json",
        )

    payload = await asyncio.to_thread(_load_json_payload, BENCHMARK_RESULTS_FILE)
    fairness = payload.get("fairness")
    if fairness is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error("Run benchmark first", code=status.HTTP_404_NOT_FOUND),
            media_type="application/json",
        )

    return JSONResponse(content=success(fairness), media_type="application/json")


async def literature_comparison_results(_admin: Any = Depends(get_current_admin)) -> JSONResponse:
    """Return the latest literature comparison report for analytics."""

    _ = _admin
    if not LITERATURE_COMPARISON_FILE.is_file():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error("Literature comparison not generated yet", code=status.HTTP_404_NOT_FOUND),
            media_type="application/json",
        )

    payload = await asyncio.to_thread(_load_json_payload, LITERATURE_COMPARISON_FILE)
    return JSONResponse(content=success(payload), media_type="application/json")


async def anomaly_results(_admin: Any = Depends(get_current_admin)) -> dict[str, Any]:
    """Return recent anomaly detections for admins."""

    _ = _admin
    return success({
        "recent_anomalies": get_recent_anomalies(limit=20),
        "total_detected": get_total_detected(),
        "monitoring_window": "last 200 incidents",
    })


async def translation_status_results(_admin: Any = Depends(get_current_admin)) -> dict[str, Any]:
    """Return loaded offline-translation model status for admins."""

    _ = _admin
    return success(await get_translation_status())


def _canonical_demand_city(city: str) -> str:
    normalized = str(city).strip().lower()
    for supported_city in CITY_BOUNDING_BOXES:
        if supported_city.lower() == normalized:
            return supported_city
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported city '{city}'. Expected one of {', '.join(CITY_BOUNDING_BOXES)}.",
    )


@limiter.limit("30/minute")
async def demand_heatmap(
    request: Request,
    city: str = Query(..., description="Target city for hotspot prediction."),
    lookahead: int = Query(30, ge=5, le=180, description="Prediction window in minutes."),
    _admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    """Return hotspot predictions and live ambulance pre-positioning recommendations."""

    _ = _admin
    canonical_city = _canonical_demand_city(city)
    density_grid = getattr(request.app.state, "density_grid", None)
    hotspots = await predict_demand(
        canonical_city,
        lookahead_minutes=lookahead,
        density_grid=density_grid,
    )
    ambulances = await AmbulanceRepository().get_all(canonical_city)
    preposition_recommendations = await recommend_preposition(
        canonical_city,
        ambulances,
        density_grid=density_grid,
        lookahead_minutes=lookahead,
        hotspots=hotspots,
    )
    return success({
        "city": canonical_city,
        "lookahead_minutes": lookahead,
        "hotspots": hotspots,
        "generated_at": isoformat_utc(),
        "preposition_recommendations": preposition_recommendations,
    })


def _frontend_response(path: str = "") -> Response:
    """Return a built frontend asset or SPA entrypoint."""

    if not FRONTEND_INDEX_FILE.is_file():
        return Response(
            content="Frontend build not found. Run `npm run build` in `frontend/`.",
            media_type="text/plain",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    requested = path.strip("/")
    first_segment = requested.split("/", 1)[0] if requested else ""
    if first_segment in FRONTEND_RESERVED_PATHS:
        raise HTTPException(status_code=404, detail="Not Found")

    if requested:
        candidate = (FRONTEND_DIST_DIR / requested).resolve()
        if FRONTEND_DIST_DIR.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)

    return FileResponse(FRONTEND_INDEX_FILE)


async def root() -> Response:
    """Serve the built frontend at the root path."""

    return _frontend_response()


async def favicon() -> Response:
    """Return a lightweight favicon so browser requests resolve with 200."""

    return Response(
        content=FAVICON_SVG,
        media_type="image/svg+xml",
        status_code=status.HTTP_200_OK,
    )


async def trigger_dispatch(
    payload: DispatchRequest,
    response: Response,
    background_tasks: BackgroundTasks,
) -> dict[str, Any] | JSONResponse:
    """Select and execute a dispatch using the formal multi-objective scorer."""

    incident = await IncidentRepository().get_by_id(payload.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    patient = await PatientRepository().get_by_id(payload.patient_id) if payload.patient_id else None

    ambulances = await AmbulanceRepository().get_all()
    hospitals = await HospitalRepository().get_all()
    triage_source = patient["chief_complaint"] if patient else incident["description"]
    triage = await triage_incident(
        triage_source,
        city=incident.get("city"),
        sos_mode=bool(patient["sos_mode"]) if patient else False,
    )
    selection_preview = await select_dispatch(
        {
            **incident,
            "type": triage["incident_type"],
            "severity": triage["severity"],
            "status": "open",
        },
        ambulances,
        hospitals,
    )
    if selection_preview["status"] == "error":
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error(selection_preview["explanation_text"], code=500)

    dispatch_result = await full_dispatch_pipeline(
        payload.incident_id,
        payload.patient_id,
        persist_dispatch=False,
    )
    if isinstance(dispatch_result, JSONResponse):
        return dispatch_result

    dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
    if dispatch_status == "error":
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error(dispatch_message or "Dispatch failed", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
    if isinstance(dispatch_plan, dict):
        dispatch_plan["ambulance_id"] = selection_preview["ambulance_id"]
        dispatch_plan["hospital_id"] = selection_preview["hospital_id"]
        dispatch_plan["eta_minutes"] = selection_preview["eta_minutes"]
        dispatch_plan["score_breakdown"] = selection_preview["score_breakdown"]
        dispatch_plan["baseline_eta_minutes"] = selection_preview["baseline_eta_minutes"]
        dispatch_plan["explanation_text"] = selection_preview["explanation_text"]
        dispatch_plan["dispatch_tier"] = selection_preview.get("dispatch_tier", dispatch_plan.get("dispatch_tier", "heuristic"))
        background_tasks.add_task(save_dispatch_bg, dispatch_plan)

    if dispatch_status == "fallback" or selection_preview["status"] == "fallback":
        response.status_code = status.HTTP_207_MULTI_STATUS
        return fallback(dispatch_plan, dispatch_message or "Fallback dispatch")

    response.status_code = status.HTTP_200_OK
    return success(dispatch_plan)


def run_migrations() -> None:
    """Apply Alembic migrations for managed PostgreSQL deployments."""

    backend_dir = Path(__file__).resolve().parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")


async def frontend_app(frontend_path: str) -> Response:
    """Serve built frontend assets and SPA fallback routes."""

    return _frontend_response(frontend_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database state and background services for the app."""

    executor = _ensure_cpu_executor()
    loop = asyncio.get_running_loop()
    loop.set_default_executor(executor)
    logger.info("CPU thread pool initialized: 4 workers")
    if settings.ENVIRONMENT == "production" and IS_POSTGRES:
        await asyncio.to_thread(run_migrations)
        logger.info("Database migrations applied")
    await initialize_database()
    inserted = await load_seed_data()
    totals = {
        "ambulances": await count_rows("ambulances"),
        "hospitals": await count_rows("hospitals"),
        "incidents": await count_rows("incidents"),
    }
    logger.info(
        "Seed sync complete (inserted: ambulances=%s, hospitals=%s, incidents=%s; totals: ambulances=%s, hospitals=%s, incidents=%s)",
        inserted["ambulances"],
        inserted["hospitals"],
        inserted["incidents"],
        totals["ambulances"],
        totals["hospitals"],
        totals["incidents"],
    )
    if LIGHTWEIGHT_TRIAGE:
        logger.info("NLP triage disabled/lightweight mode active; skipping Hugging Face model preloading.")
    else:
        logger.info("NLP triage model loading in background... First run may download about 1.6GB.")
        from services.nlp_triage import _get_classifier

        async def _preload_nlp_triage_model() -> None:
            try:
                await asyncio.to_thread(_get_classifier)
            except Exception as exc:
                logger.warning("NLP triage model preload failed: %s", exc)

        asyncio.create_task(_preload_nlp_triage_model())
        if settings.ENABLE_TRANSLATION:
            from services.offline_translator import _load_translation_pipeline

            async def _preload_hindi_translation_model() -> None:
                try:
                    await asyncio.to_thread(_load_translation_pipeline, "Helsinki-NLP/opus-mt-hi-en")
                except Exception as exc:
                    logger.warning("Hindi translation model preload failed: %s", exc)

            logger.info("Hindi translation model preloading in background...")
            asyncio.create_task(_preload_hindi_translation_model())
    app.state.density_grid = await asyncio.to_thread(build_density_grid)
    app.state.simulation_engine = SimulationEngine()
    if DISABLE_SIMULATION:
        logger.info("Background simulation loop disabled by RAID_DISABLE_SIMULATION.")
    else:
        await app.state.simulation_engine.start()
    try:
        yield
    finally:
        simulation_engine = getattr(app.state, "simulation_engine", None)
        if simulation_engine is not None:
            await simulation_engine.stop()
        await close_connection()
        if not getattr(CPU_EXECUTOR, "_shutdown", False):
            CPU_EXECUTOR.shutdown(wait=True)
            logger.info("CPU thread pool shut down cleanly")


def create_app() -> FastAPI:
    """Build and configure the RAID Nexus FastAPI application."""

    application = FastAPI(
        title="RAID Nexus",
        version="0.1.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(TimingMiddleware)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, global_exception_handler)

    application.include_router(websocket_router)
    application.include_router(auth_router, prefix="/api")
    application.include_router(ambulances_router, prefix="/api")
    application.include_router(hospitals_router, prefix="/api")
    application.include_router(incidents_router, prefix="/api")
    application.include_router(patients_router, prefix="/api")
    application.include_router(dispatch_router, prefix="/api")
    application.include_router(overrides_router, prefix="/api")
    application.include_router(system_router, prefix="/api")
    application.add_api_route("/api/dispatch", trigger_dispatch, methods=["POST"], response_model=None)
    application.add_api_route("/api/benchmark", benchmark_results, methods=["GET"], response_model=None)
    application.add_api_route("/api/fairness", fairness_results, methods=["GET"], response_model=None)
    application.add_api_route(
        "/api/literature-comparison",
        literature_comparison_results,
        methods=["GET"],
        response_model=None,
    )
    application.add_api_route("/api/anomalies", anomaly_results, methods=["GET"], response_model=None)
    application.add_api_route(
        "/api/translation/status",
        translation_status_results,
        methods=["GET"],
        response_model=None,
    )
    application.add_api_route("/api/demand/heatmap", demand_heatmap, methods=["GET"], response_model=None)
    application.add_api_route("/", root, methods=["GET"], include_in_schema=False)
    application.add_api_route("/favicon.ico", favicon, methods=["GET"], include_in_schema=False)
    application.add_api_route("/health", health, methods=["GET"])
    application.add_api_route("/{frontend_path:path}", frontend_app, methods=["GET"], include_in_schema=False)
    return application


app = create_app()
