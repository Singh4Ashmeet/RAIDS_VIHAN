"""
RAID Nexus unified launcher.

Usage:
  python start.py [--port-backend 8000] [--port-frontend 5173]

Starts the FastAPI backend and React/Vite frontend together, wires the
frontend to the selected backend through VITE_API_BASE_URL, and prints the
current application routes for the admin and user portals.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

if load_dotenv is not None:
    load_dotenv(BACKEND / ".env")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

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
            print(f"  {color}[{label}]{RESET} {text}")


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


def start_backend(port: int, host: str, python_cmd: str) -> subprocess.Popen:
    print(f"  {GREEN}[BACKEND]{RESET} Starting FastAPI on http://{host}:{port}...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
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


def admin_auth_headers(backend_url: str) -> dict[str, str] | None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    body = urlencode({"username": username, "password": password}).encode("utf-8")
    try:
        request = Request(
            f"{backend_url}/api/auth/login",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        token = token_payload.get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    except Exception as exc:
        print(f"  {YELLOW}[WARN]{RESET} Admin login check failed: {exc}")
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
        ("Analytics", f"{backend_url}/api/analytics", None),
        ("Benchmark", f"{backend_url}/api/benchmark", None),
        (
            "Demand Heatmap",
            f"{backend_url}/api/demand/heatmap?city=Bengaluru&lookahead=30",
            admin_headers,
        ),
    ]
    for label, url, headers in checks:
        ok, status_text = http_status(url, headers=headers)
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
    args = parser.parse_args()

    banner()
    check_dirs()
    check_frontend_dependencies()
    warn_if_benchmark_missing()
    warn_if_synthetic_incidents_missing()

    python_cmd = find_python()
    npm_cmd = find_npm()
    backend_port = args.port_backend
    frontend_port = args.port_frontend
    backend_url = f"http://{args.host_backend}:{backend_port}"

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
            backend_proc = start_backend(backend_port, args.host_backend, python_cmd)
            backend_owned = True
            processes.append(backend_proc)
    else:
        backend_proc = start_backend(backend_port, args.host_backend, python_cmd)
        backend_owned = True
        processes.append(backend_proc)

    if backend_owned:
        print(f"  {GREEN}[BACKEND]{RESET} Waiting for API health...")
        if wait_for_http(f"{backend_url}/health", timeout=45, label="backend"):
            print(f"  {GREEN}[BACKEND]{RESET} {BOLD}Ready{RESET} - {backend_url}/docs\n")

    if not args.skip_frontend:
        if is_port_open(args.host_frontend, frontend_port):
            frontend_port = find_available_port(args.host_frontend, frontend_port + 1)
            print(
                f"  {YELLOW}[FRONTEND]{RESET} Port {args.port_frontend} is in use; "
                f"starting Vite on {frontend_port}."
            )
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
