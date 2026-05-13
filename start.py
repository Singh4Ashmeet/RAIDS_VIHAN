"""
RAID Nexus unified launcher.

Usage:
  python start.py [--port-backend 8000] [--port-frontend 5173]

Starts the FastAPI backend and React/Vite frontend together, wires the
frontend to the selected backend through VITE_API_BASE_URL, and prints the
current application routes for the admin and user portals. Optional C++,
Java, and C# modules are detected and verified without blocking the main app.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
OPTIMIZER_CPP = ROOT / "optimizer_cpp"
JAVA_DRIVER = ROOT / "mobile_driver_java"
CSHARP_SIMULATION = ROOT / "simulation_csharp"
CPP_BUILD_DIR = OPTIMIZER_CPP / "build"
CPP_OPTIMIZER = CPP_BUILD_DIR / ("raid_optimizer.exe" if os.name == "nt" else "raid_optimizer")
CPP_RELEASE_OPTIMIZER = CPP_BUILD_DIR / "Release" / ("raid_optimizer.exe" if os.name == "nt" else "raid_optimizer")
JAVA_DRIVER_CLIENT = JAVA_DRIVER / "src" / "main" / "java" / "in" / "raidnexus" / "driver" / "DriverClient.java"
CSHARP_PROJECT = CSHARP_SIMULATION / "RaidNexusSimulation.csproj"


def load_env_file(env_path: Path) -> None:
    """Load backend .env values even before optional dependencies are installed."""

    try:
        dotenv = importlib.import_module("dotenv")
        load_dotenv = getattr(dotenv, "load_dotenv", None)
    except ModuleNotFoundError:
        load_dotenv = None

    if callable(load_dotenv):
        load_dotenv(env_path)
        return

    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


load_env_file(BACKEND / ".env")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(errors="replace", line_buffering=True)
        except Exception:
            pass

ADMIN_ROUTES = [
    "/admin/command",
    "/admin/fleet",
    "/admin/analytics",
    "/admin/scenario",
    "/admin/heatmap",
]

USER_ROUTES = [
    "/user/sos",
    "/user/status",
    "/user/hospitals",
]

API_ENDPOINTS = [
    ("Health", "/health", False),
    ("Ambulances", "/api/ambulances", False),
    ("Hospitals", "/api/hospitals", False),
    ("Incidents", "/api/incidents", False),
    ("Analytics", "/api/analytics", False),
    ("Benchmark", "/api/benchmark", False),
    ("Demand Heatmap", "/api/demand/heatmap?city=Bengaluru&lookahead=30", True),
    ("Scenario Lab", "/api/simulate/scenario", False),
]


def banner() -> None:
    print(
        f"""
{BOLD}{CYAN}
  RAID NEXUS
  Real-time AI-powered ambulance dispatch dashboard
{RESET}  {YELLOW}Admin + user portals, benchmark analytics, demand heatmap, WebSocket live state{RESET}
"""
    )


def prefix_stream(proc: subprocess.Popen, label: str, color: str) -> None:
    if proc.stdout is None:
        return
    for line in iter(proc.stdout.readline, b""):
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            output = f"  {color}[{label}]{RESET} {text}"
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            safe_output = output.encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(safe_output, flush=True)


def check_dirs() -> None:
    if not BACKEND.is_dir():
        print(f"{RED}ERROR: backend/ not found at {BACKEND}{RESET}")
        sys.exit(1)
    if not FRONTEND.is_dir():
        print(f"{RED}ERROR: frontend/ not found at {FRONTEND}{RESET}")
        sys.exit(1)


def find_python() -> str:
    candidates = [
        ROOT / "venv" / "Scripts" / "python.exe",
        BACKEND / "venv" / "Scripts" / "python.exe",
        Path(sys.executable),
        Path("python3"),
        Path("python"),
    ]
    for candidate in candidates:
        command = str(candidate)
        try:
            result = subprocess.run([command, "--version"], capture_output=True, timeout=3)
            if result.returncode == 0:
                return command
        except Exception:
            continue
    return "python"


def find_npm() -> str:
    for candidate in ["npm.cmd", "npm", r"C:\Program Files\nodejs\npm.cmd"]:
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return candidate
        except Exception:
            continue
    print(f"{RED}ERROR: npm not found. Install Node.js 18+ and run npm install in frontend/.{RESET}")
    sys.exit(1)


def find_tool(*names: str) -> str | None:
    """Return the first executable found on PATH."""

    for name in names:
        candidate = shutil.which(name)
        if candidate:
            return candidate
    if os.name == "nt" and not getattr(find_tool, "_path_refreshed", False):
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
                    "[Environment]::GetEnvironmentVariable('Path','User')",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                os.environ["PATH"] = completed.stdout.strip()
        except Exception:
            pass
        setattr(find_tool, "_path_refreshed", True)
        for name in names:
            candidate = shutil.which(name)
            if candidate:
                return candidate
    return None


def run_capture(
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a helper command and return success plus compact output."""

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return False, str(exc)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout}s"

    output = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part and part.strip()
    )
    return completed.returncode == 0, output or f"exit={completed.returncode}"


def ensure_cpp_optimizer(build_optional: bool) -> tuple[bool, str]:
    """Ensure the optional C++ optimizer binary exists."""

    if CPP_OPTIMIZER.is_file():
        return True, str(CPP_OPTIMIZER)
    if CPP_RELEASE_OPTIMIZER.is_file():
        CPP_BUILD_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CPP_RELEASE_OPTIMIZER, CPP_OPTIMIZER)
        return True, str(CPP_OPTIMIZER)
    if not build_optional:
        return False, "raid_optimizer binary not found; build skipped"

    cmake = find_tool("cmake")
    if cmake is None:
        return False, "cmake not found"

    configure = [cmake, "-S", str(OPTIMIZER_CPP), "-B", str(CPP_BUILD_DIR)]
    generator = os.getenv("RAID_CMAKE_GENERATOR")
    arch = os.getenv("RAID_CMAKE_ARCH")
    if generator:
        configure.extend(["-G", generator])
    if arch:
        configure.extend(["-A", arch])

    ok, output = run_capture(configure, timeout=180)
    if not ok:
        return False, f"CMake configure failed: {output.splitlines()[-1] if output else 'unknown error'}"

    ok, output = run_capture([cmake, "--build", str(CPP_BUILD_DIR), "--config", "Release"], timeout=240)
    if not ok:
        return False, f"CMake build failed: {output.splitlines()[-1] if output else 'unknown error'}"

    if CPP_RELEASE_OPTIMIZER.is_file():
        shutil.copy2(CPP_RELEASE_OPTIMIZER, CPP_OPTIMIZER)
    if CPP_OPTIMIZER.is_file():
        return True, str(CPP_OPTIMIZER)
    return False, "C++ build completed but raid_optimizer was not found"


def verify_cpp_connection(python_cmd: str, build_optional: bool) -> tuple[bool, str]:
    """Verify FastAPI can reach the optional C++ optimizer through the adapter."""

    ok, detail = ensure_cpp_optimizer(build_optional)
    if not ok:
        return False, detail

    probe = f"""
import sys
sys.path.insert(0, {str(BACKEND)!r})
from services.cpp_adapter import optimize_dispatch
result = optimize_dispatch(
    {{"id": "INC-START", "location_lat": 28.6139, "location_lng": 77.2090}},
    [
        {{"id": "AMB-FAR", "status": "available", "lat": 28.8, "lng": 77.3}},
        {{"id": "AMB-NEAR", "status": "available", "lat": 28.614, "lng": 77.209}},
    ],
)
assignment = result.get("assignment") or {{}}
print(result.get("status"), assignment.get("ambulance_id"), assignment.get("optimizer"))
"""
    ok, output = run_capture([python_cmd, "-c", probe], timeout=30)
    if ok and "success AMB-NEAR" in output:
        return True, output.strip()
    return False, output.strip()


def verify_java_connection() -> tuple[bool, str]:
    """Compile-check the Java driver client scaffold."""

    if not JAVA_DRIVER_CLIENT.is_file():
        return False, f"{JAVA_DRIVER_CLIENT} not found"
    javac = find_tool("javac")
    if javac is None:
        return False, "javac not found"

    with tempfile.TemporaryDirectory(prefix="raid-java-") as temp_dir:
        ok, output = run_capture(
            [javac, "-d", temp_dir, str(JAVA_DRIVER_CLIENT)],
            timeout=60,
        )
    if ok:
        return True, "DriverClient.java compiled"
    return False, output.splitlines()[-1] if output else "javac failed"


def verify_csharp_connection(backend_url: str) -> tuple[bool, str]:
    """Build and run the C# simulation scaffold against the active backend."""

    if not CSHARP_PROJECT.is_file():
        return False, f"{CSHARP_PROJECT} not found"
    dotnet = find_tool("dotnet")
    if dotnet is None:
        return False, "dotnet not found"

    env = os.environ.copy()
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    with tempfile.TemporaryDirectory(prefix="raid-dotnet-out-") as out_dir, tempfile.TemporaryDirectory(
        prefix="raid-dotnet-obj-"
    ) as obj_dir:
        out_path = Path(out_dir)
        obj_path = Path(obj_dir)
        ok, output = run_capture(
            [
                dotnet,
                "build",
                str(CSHARP_PROJECT),
                "-c",
                "Release",
                "-o",
                str(out_path),
                f"/p:BaseIntermediateOutputPath={obj_path}{os.sep}",
                f"/p:IntermediateOutputPath={obj_path}{os.sep}intermediate{os.sep}",
            ],
            timeout=180,
            env=env,
        )
        if not ok:
            return False, output.splitlines()[-1] if output else "dotnet build failed"

        (out_path / "appsettings.json").write_text(
            json.dumps({"API_BASE_URL": backend_url}, indent=2),
            encoding="utf-8",
        )
        dll_path = out_path / "RaidNexusSimulation.dll"
        ok, output = run_capture([dotnet, str(dll_path)], cwd=out_path, timeout=30, env=env)
    if ok and ": ok" in output:
        return True, output.strip()
    return False, output.strip()


def verify_multilanguage_connections(
    backend_url: str,
    python_cmd: str,
    *,
    build_optional: bool,
) -> None:
    """Run non-blocking C++, Java, and C# module connection checks."""

    print(f"\n{BOLD}Checking multi-language connections...{RESET}")
    checks = [
        ("C++ optimizer", lambda: verify_cpp_connection(python_cmd, build_optional)),
        ("Java driver", verify_java_connection),
        ("C# simulation", lambda: verify_csharp_connection(backend_url)),
    ]
    for label, check in checks:
        ok, detail = check()
        color = GREEN if ok else YELLOW
        prefix = "OK" if ok else "WARN"
        print(f"  {color}[{prefix}] {label:<14}{RESET} {detail}")


def check_frontend_dependencies() -> None:
    if not (FRONTEND / "node_modules").is_dir():
        print(f"  {YELLOW}[WARN]{RESET} frontend/node_modules not found. Running npm install first may be required.")


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_available_port(host: str, preferred_port: int, max_attempts: int = 20) -> int:
    for offset in range(max_attempts):
        candidate = preferred_port + offset
        if not is_port_open(host, candidate):
            return candidate
    raise RuntimeError(
        f"No available port found from {preferred_port} to {preferred_port + max_attempts - 1}."
    )


def start_backend(
    port: int,
    host: str,
    python_cmd: str,
    *,
    frontend_url: str | None = None,
) -> subprocess.Popen:
    print(f"  {GREEN}[BACKEND]{RESET} Starting FastAPI on http://{host}:{port}...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if frontend_url:
        configured_origins = env.get("CORS_ORIGINS", "")
        origins = [
            origin.strip()
            for origin in configured_origins.split(",")
            if origin.strip()
        ]
        if frontend_url not in origins:
            origins.append(frontend_url)
        env["CORS_ORIGINS"] = ",".join(origins)
    env.setdefault("RAID_DISABLE_SIMULATION", "false")
    env.setdefault("RAID_DISABLE_EXTERNAL_ROUTING", "1")
    env.setdefault("RAID_DISABLE_ROUTE_GEOMETRY", "0")
    env.setdefault("RAID_LIGHTWEIGHT_TRIAGE", "1")
    env.setdefault("ENABLE_NLP_TRIAGE", "false")
    env.setdefault("ENABLE_TRANSLATION", "false")
    env.setdefault("USE_LLM", "false")
    proc = subprocess.Popen(
        [
            python_cmd,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            host,
            "--port",
            str(port),
            "--reload",
        ],
        cwd=BACKEND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    threading.Thread(target=prefix_stream, args=(proc, "API", GREEN), daemon=True).start()
    return proc


def start_frontend(
    port: int,
    host: str,
    backend_url: str,
    npm_cmd: str,
) -> subprocess.Popen:
    print(f"  {CYAN}[FRONTEND]{RESET} Starting Vite on http://{host}:{port}...")
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = backend_url
    env["VITE_WS_URL"] = f"{backend_url.replace('http', 'ws', 1)}/ws/live"
    env["VITE_WS_BASE_URL"] = backend_url.replace("http", "ws", 1)
    proc = subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--host", host, "--port", str(port)],
        cwd=FRONTEND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    threading.Thread(target=prefix_stream, args=(proc, "UI", CYAN), daemon=True).start()
    return proc


def wait_for_port(host: str, port: int, timeout: int = 30, label: str = "service") -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    print(f"  {YELLOW}[WARN]{RESET} {label} on {host}:{port} did not respond in {timeout}s")
    return False


def http_status(url: str, headers: dict[str, str] | None = None, timeout: int = 5) -> tuple[bool, str]:
    try:
        request = Request(url, headers=headers or {})
        with urlopen(request, timeout=timeout) as response:
            return True, str(response.status)
    except HTTPError as exc:
        return False, str(exc.code)
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:
        return False, str(exc)


def retry_http_status(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    timeout: int = 10,
    attempts: int = 4,
    delay: float = 0.75,
) -> tuple[bool, str]:
    """Retry transient startup-time HTTP checks before reporting status."""

    last_status = ""
    for _ in range(attempts):
        ok, status_text = http_status(url, headers=headers, timeout=timeout)
        if ok:
            return True, status_text
        last_status = status_text
        time.sleep(delay)
    return False, last_status


def admin_auth_headers(backend_url: str) -> dict[str, str] | None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    body = urlencode({"username": username, "password": password}).encode("utf-8")
    last_error = "unknown error"
    for _ in range(4):
        try:
            request = Request(
                f"{backend_url}/api/auth/login",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            token_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            token = token_payload.get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}
            last_error = "token missing"
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.75)
    print(f"  {YELLOW}[WARN]{RESET} Admin login check failed after retries: {last_error}")
    return None


def wait_for_http(url: str, timeout: int = 30, label: str = "service") -> bool:
    start = time.time()
    while time.time() - start < timeout:
        ok, _ = http_status(url, timeout=2)
        if ok:
            return True
        time.sleep(0.5)
    print(f"  {YELLOW}[WARN]{RESET} {label} did not return HTTP 200 in {timeout}s")
    return False


def print_endpoint_map(backend_url: str, frontend_url: str) -> None:
    print(f"\n{BOLD}Connected surfaces{RESET}")
    print(f"  {GREEN}Backend health:{RESET}     {backend_url}/health")
    print(f"  {GREEN}API docs:{RESET}           {backend_url}/docs")
    print(f"  {CYAN}Frontend:{RESET}           {frontend_url}")
    print(f"  {CYAN}WebSocket:{RESET}          managed by the logged-in app")
    print(f"  {CYAN}WebSocket endpoint:{RESET} {backend_url.replace('http', 'ws', 1)}/ws/live?token=<access_token>")
    print(f"  {YELLOW}Note:{RESET} ws:// URLs cannot be opened as normal browser pages.")

    print(f"\n{BOLD}Admin portal{RESET}")
    for route in ADMIN_ROUTES:
        print(f"  {CYAN}{frontend_url}{route}{RESET}")

    print(f"\n{BOLD}User portal{RESET}")
    for route in USER_ROUTES:
        print(f"  {CYAN}{frontend_url}{route}{RESET}")

    print(f"\n{BOLD}Backend API connections{RESET}")
    for label, path, requires_admin in API_ENDPOINTS:
        suffix = " (admin token)" if requires_admin else ""
        print(f"  {GREEN}{label:<14}{RESET} {backend_url}{path}{suffix}")


def verify_core_endpoints(backend_url: str) -> None:
    print(f"\n{BOLD}Checking backend connections...{RESET}")
    admin_headers = admin_auth_headers(backend_url)
    checks = [
        ("Health", f"{backend_url}/health", None),
        ("OpenAPI", f"{backend_url}/openapi.json", None),
        ("API Docs", f"{backend_url}/docs", None),
        ("Analytics", f"{backend_url}/api/analytics", None),
        ("Benchmark", f"{backend_url}/api/benchmark", None),
        (
            "Demand Heatmap",
            f"{backend_url}/api/demand/heatmap?city=Bengaluru&lookahead=30",
            admin_headers,
        ),
    ]
    for label, url, headers in checks:
        ok, status_text = retry_http_status(url, headers=headers, timeout=10, attempts=4)
        color = GREEN if ok else YELLOW
        print(f"  {color}[{label}]{RESET} {status_text}")


def verify_frontend_routes(frontend_url: str) -> None:
    print(f"\n{BOLD}Checking frontend routes...{RESET}")
    for route in ["/admin/scenario", "/admin/heatmap", "/user/sos"]:
        ok, status_text = http_status(f"{frontend_url}{route}")
        color = GREEN if ok else YELLOW
        print(f"  {color}[{route}]{RESET} {status_text}")


def warn_if_benchmark_missing() -> None:
    benchmark_file = BACKEND / "data" / "benchmark_results.json"
    if not benchmark_file.is_file():
        print(
            f"  {YELLOW}[WARN]{RESET} Benchmark results not found. "
            "Run: python backend/scripts/benchmark.py"
        )


def warn_if_synthetic_incidents_missing() -> None:
    incidents_file = BACKEND / "data" / "synthetic_incidents.json"
    if not incidents_file.is_file():
        print(
            f"  {YELLOW}[WARN]{RESET} Demand heatmap training data not found. "
            "Run: python backend/scripts/generate_incidents.py --count 500"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="RAID Nexus launcher")
    parser.add_argument("--port-backend", type=int, default=8000)
    parser.add_argument("--port-frontend", type=int, default=5173)
    parser.add_argument("--host-backend", default="127.0.0.1")
    parser.add_argument("--host-frontend", default="127.0.0.1")
    parser.add_argument("--skip-frontend", action="store_true", help="Start backend only")
    parser.add_argument("--skip-checks", action="store_true", help="Skip post-start HTTP checks")
    parser.add_argument("--skip-multilang", action="store_true", help="Skip optional C++/Java/C# checks")
    parser.add_argument(
        "--enable-simulation",
        action="store_true",
        help="Compatibility flag; simulation is enabled by default for Scenario Lab",
    )
    parser.add_argument(
        "--disable-simulation",
        action="store_true",
        help="Disable the background simulation loop during local startup",
    )
    parser.add_argument(
        "--enable-heavy-ai",
        action="store_true",
        help="Allow NLP and translation model preloads during local startup",
    )
    parser.add_argument(
        "--enable-external-routing",
        action="store_true",
        help="Allow live OSRM route lookups instead of deterministic local fallback routing",
    )
    parser.add_argument(
        "--disable-route-geometry",
        action="store_true",
        help="Use straight-line map fallbacks instead of OSRM road polylines",
    )
    parser.add_argument(
        "--skip-optional-builds",
        action="store_true",
        help="Do not build optional C++/.NET modules during startup checks",
    )
    args = parser.parse_args()

    banner()
    check_dirs()
    check_frontend_dependencies()
    warn_if_benchmark_missing()
    warn_if_synthetic_incidents_missing()

    os.environ.setdefault("USE_LLM", "false")
    os.environ["RAID_DISABLE_SIMULATION"] = "1" if args.disable_simulation else "false"
    os.environ["RAID_DISABLE_EXTERNAL_ROUTING"] = (
        "0" if args.enable_external_routing else "1"
    )
    os.environ["RAID_DISABLE_ROUTE_GEOMETRY"] = "1" if args.disable_route_geometry else "0"
    os.environ["RAID_LIGHTWEIGHT_TRIAGE"] = "0" if args.enable_heavy_ai else "1"
    os.environ["ENABLE_NLP_TRIAGE"] = "true" if args.enable_heavy_ai else "false"
    os.environ["ENABLE_TRANSLATION"] = "true" if args.enable_heavy_ai else "false"

    python_cmd = find_python()
    npm_cmd = find_npm()
    backend_port = args.port_backend
    frontend_port = args.port_frontend
    if not args.skip_frontend and is_port_open(args.host_frontend, frontend_port):
        frontend_port = find_available_port(args.host_frontend, frontend_port + 1)
        print(
            f"  {YELLOW}[FRONTEND]{RESET} Port {args.port_frontend} is in use; "
            f"planning Vite on {frontend_port}."
        )
    backend_url = f"http://{args.host_backend}:{backend_port}"
    frontend_url = f"http://{args.host_frontend}:{frontend_port}"

    processes: list[subprocess.Popen] = []
    print(f"{BOLD}Starting services...{RESET}\n")

    backend_owned = False
    if is_port_open(args.host_backend, backend_port):
        ok, status_text = http_status(f"{backend_url}/health", timeout=2)
        if ok:
            print(
                f"  {YELLOW}[BACKEND]{RESET} Port {backend_port} is already serving RAID Nexus "
                f"({status_text}); reusing {backend_url}."
            )
            print(f"  {GREEN}[BACKEND]{RESET} {BOLD}Ready{RESET} - {backend_url}/docs\n")
        else:
            backend_port = find_available_port(args.host_backend, backend_port + 1)
            backend_url = f"http://{args.host_backend}:{backend_port}"
            print(
                f"  {YELLOW}[BACKEND]{RESET} Port {args.port_backend} is occupied but /health failed "
                f"({status_text}); using {backend_port} instead."
            )
            backend_proc = start_backend(
                backend_port,
                args.host_backend,
                python_cmd,
                frontend_url=frontend_url if not args.skip_frontend else None,
            )
            backend_owned = True
            processes.append(backend_proc)
    else:
        backend_proc = start_backend(
            backend_port,
            args.host_backend,
            python_cmd,
            frontend_url=frontend_url if not args.skip_frontend else None,
        )
        backend_owned = True
        processes.append(backend_proc)

    if backend_owned:
        print(f"  {GREEN}[BACKEND]{RESET} Waiting for API health...")
        if wait_for_http(f"{backend_url}/health", timeout=45, label="backend"):
            print(f"  {GREEN}[BACKEND]{RESET} {BOLD}Ready{RESET} - {backend_url}/docs\n")

    if not args.skip_multilang:
        verify_multilanguage_connections(
            backend_url,
            python_cmd,
            build_optional=not args.skip_optional_builds,
        )

    if not args.skip_frontend:
        frontend_url = f"http://{args.host_frontend}:{frontend_port}"
        frontend_proc = start_frontend(frontend_port, args.host_frontend, backend_url, npm_cmd)
        processes.append(frontend_proc)
        print(f"  {CYAN}[FRONTEND]{RESET} Waiting for Vite...")
        if wait_for_port(args.host_frontend, frontend_port, timeout=45, label="frontend"):
            print(f"  {CYAN}[FRONTEND]{RESET} {BOLD}Ready{RESET} - {frontend_url}\n")
    else:
        frontend_url = f"http://{args.host_frontend}:{frontend_port}"

    if not args.skip_checks:
        verify_core_endpoints(backend_url)
        if not args.skip_frontend:
            verify_frontend_routes(frontend_url)

    print_endpoint_map(backend_url, frontend_url)
    print(f"\n{BOLD}RAID Nexus is running{RESET}")
    print(f"  Press {BOLD}Ctrl+C{RESET} to stop all services\n")
    print("-" * 72)

    def shutdown(signum: int | None = None, frame: object | None = None) -> None:
        _ = signum, frame
        print(f"\n\n{YELLOW}Shutting down RAID Nexus...{RESET}")
        for process in processes:
            try:
                process.terminate()
            except Exception:
                pass
        time.sleep(1)
        for process in processes:
            try:
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        print(f"{GREEN}All services stopped.{RESET}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        uptime_seconds = 0
        while True:
            time.sleep(5)
            for process in list(processes):
                if process.poll() is not None:
                    print(
                        f"\n{RED}[WARN] A service exited unexpectedly "
                        f"(code {process.returncode}). Check output above.{RESET}"
                    )
                    processes.remove(process)
                    if not processes:
                        print(f"{RED}All services have stopped.{RESET}")
                        sys.exit(1)
            uptime_seconds += 5
            if uptime_seconds % 60 == 0:
                print(
                    f"  {GREEN}[RAID]{RESET} Running - "
                    f"{len(processes)} service(s) - uptime {uptime_seconds // 60}m"
                )
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
