"""Start each backend service briefly and report startup status."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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


def request_health(port: int) -> tuple[bool, str]:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read().decode("utf-8", errors="replace")
            return 200 <= response.status < 300, f"{response.status} {body}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"{exc.code} {body}"
    except Exception as exc:
        return False, repr(exc)


def run_service(service: str, port: int) -> tuple[str, int | None, bool, str, str]:
    proc = subprocess.Popen(
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

    health_ok = False
    health_output = "not checked"
    deadline = time.time() + 25
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


def main() -> int:
    failed = False
    for service, port in SERVICES:
        name, code, health_ok, health_output, output = run_service(service, port)
        if code is None and health_ok:
            print(f"## {name}: stayed up and passed /health")
        else:
            failed = True
            status = f"exited with {code}" if code is not None else "failed /health"
            print(f"## {name}: {status}")
        print(f"/health: {health_output}")
        print(output[-4000:])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
