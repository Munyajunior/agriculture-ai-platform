"""Start backend services for smoke checks or local development."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SERVICES = [
    ("api-gateway", 8000),
    ("auth-service", 8001),
    ("ai-service", 8002),
    ("analytics-service", 8003),
    ("media-service", 8004),
    ("model-registry", 8005),
    ("sync-service", 8006),
]


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def service_env(service: str) -> dict[str, str]:
    env = os.environ.copy()
    paths = [
        ROOT / ".venv" / "Lib" / "site-packages",
        ROOT / "services" / service,
        ROOT / "shared" / "types",
        ROOT / "shared" / "inference-sdk",
    ]
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in paths)
    env.update(load_dotenv(ROOT / "services" / service / ".env"))
    env.setdefault("SECRET_KEY", "abcdefghijklmnopqrstuvwxyz123456")
    env.setdefault("STORAGE_TYPE", "local")
    return env


def start_service_process(service: str, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--lifespan",
            "on",
        ],
        cwd=ROOT / "services" / service,
        env=service_env(service),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def request_health(port: int) -> tuple[bool, str]:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with LOCAL_OPENER.open(url, timeout=2) as response:
            body = response.read().decode("utf-8", errors="replace")
            return 200 <= response.status < 300, f"{response.status} {body}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"{exc.code} {body}"
    except Exception as exc:
        return False, repr(exc)


def run_service(service: str, port: int, timeout: int) -> tuple[str, int | None, bool, str, str]:
    proc = start_service_process(service, port)

    health_ok = False
    health_output = "not checked"
    deadline = time.time() + timeout
    while time.time() < deadline:
        code = proc.poll()
        if code is not None:
            output, _ = proc.communicate()
            return service, code, health_ok, health_output, output

        health_ok, health_output = request_health(port)
        if health_ok:
            break
        time.sleep(0.5)

    code = proc.poll()
    if code is None:
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
        return service, None, health_ok, health_output, output

    output, _ = proc.communicate()
    return service, code, health_ok, health_output, output


def wait_for_health(service: str, port: int, proc: subprocess.Popen[str], timeout: int) -> tuple[bool, str]:
    deadline = time.time() + timeout
    health_output = "not checked"
    while time.time() < deadline:
        code = proc.poll()
        if code is not None:
            return False, f"process exited with {code}"

        health_ok, health_output = request_health(port)
        if health_ok:
            return True, health_output
        time.sleep(0.5)

    return False, health_output


def stream_output(service: str, proc: subprocess.Popen[str]) -> None:
    if proc.stdout is None:
        return
    for line in proc.stdout:
        print(f"[{service}] {line}", end="")


def terminate_processes(processes: list[tuple[str, subprocess.Popen[str]]]) -> None:
    for service, proc in processes:
        if proc.poll() is None:
            print(f"Stopping {service}...")
            proc.terminate()

    for service, proc in processes:
        if proc.poll() is not None:
            continue
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"Force stopping {service}...")
            proc.kill()


def run_keep_alive(timeout: int) -> int:
    processes: list[tuple[str, subprocess.Popen[str]]] = []
    failed = False

    try:
        for service, port in SERVICES:
            print(f"Starting {service} on http://127.0.0.1:{port} ...")
            proc = start_service_process(service, port)
            processes.append((service, proc))
            threading.Thread(target=stream_output, args=(service, proc), daemon=True).start()

            health_ok, health_output = wait_for_health(service, port, proc, timeout)
            if health_ok:
                print(f"## {service}: running and passed /health")
            else:
                failed = True
                print(f"## {service}: failed startup")
            print(f"/health: {health_output}")

        if failed:
            return 1

        print("")
        print("Backend is running. Open http://127.0.0.1:8000/health or http://127.0.0.1:8000/api/docs")
        print("Press Ctrl+C to stop all local backend services.")
        while True:
            dead = [(service, proc.poll()) for service, proc in processes if proc.poll() is not None]
            if dead:
                for service, code in dead:
                    print(f"{service} exited with {code}")
                return 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("")
        print("Shutdown requested.")
        return 0
    finally:
        terminate_processes(processes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep all backend services running until Ctrl+C after health checks pass.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Seconds to wait for each service health check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.keep_alive:
        return run_keep_alive(args.timeout)

    failed = False
    for service, port in SERVICES:
        name, code, health_ok, health_output, output = run_service(service, port, args.timeout)
        if code is None and health_ok:
            print(f"## {name}: started, passed /health, and was stopped")
        else:
            failed = True
            status = f"exited with {code}" if code is not None else "failed /health"
            print(f"## {name}: {status}")
        print(f"/health: {health_output}")
        print(output[-4000:])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
