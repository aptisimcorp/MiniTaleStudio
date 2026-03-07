"""
MiniTaleStudio Aspire - Local Development Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Single command to launch the entire platform:

    python aspire.py

Similar to .NET Aspire, this orchestrator:
  - Runs pre-flight checks (dependencies, connectivity)
  - Starts all services (Backend, Celery Worker, Celery Beat, Frontend)
  - Multiplexes colored logs from every service into one terminal
  - Monitors health and shows a live dashboard
  - Handles graceful shutdown on Ctrl+C
"""

import os
import sys
import signal
import subprocess
import threading
import time
import json
import socket
from pathlib import Path
from datetime import datetime

# ?? Resolve project root ????????????????????????????????????????????????
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
ENV_FILE = ROOT / ".env"

# ?? ANSI Colors ?????????????????????????????????????????????????????????
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_GREEN  = "\033[42m"
    BG_RED    = "\033[41m"
    BG_BLUE   = "\033[44m"
    BG_YELLOW = "\033[43m"

# ?? Service Definitions ?????????????????????????????????????????????????
SERVICES = [
    {
        "name": "Backend",
        "tag": "API",
        "color": C.CYAN,
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "0.0.0.0", "--port", "8000", "--reload"],
        "cwd": str(BACKEND_DIR),
        "url": "http://localhost:8000",
        "health": "http://localhost:8000/",
    },
    {
        "name": "Celery Worker",
        "tag": "WRK",
        "color": C.MAGENTA,
        "cmd": [sys.executable, "-m", "celery",
                "-A", "app.workers.celery_app", "worker",
                "--loglevel=info", "--pool=solo"],
        "cwd": str(BACKEND_DIR),
        "url": None,
        "health": None,
    },
    {
        "name": "Celery Beat",
        "tag": "SCH",
        "color": C.YELLOW,
        "cmd": [sys.executable, "-m", "celery",
                "-A", "app.workers.celery_app", "beat",
                "--loglevel=info"],
        "cwd": str(BACKEND_DIR),
        "url": None,
        "health": None,
    },
    {
        "name": "Frontend",
        "tag": "WEB",
        "color": C.GREEN,
        "cmd": ["npx", "react-scripts", "start"] if sys.platform != "win32"
               else ["cmd", "/c", "npx", "react-scripts", "start"],
        "cwd": str(FRONTEND_DIR),
        "url": "http://localhost:3000",
        "health": "http://localhost:3000/",
    },
]

# ?? Globals ??????????????????????????????????????????????????????????????
processes: list[subprocess.Popen] = []
shutdown_event = threading.Event()

# ?? Helpers ??????????????????????????????????????????????????????????????

def banner():
    print(f"""
{C.BOLD}{C.CYAN}
    __  ____      _ ______      __   _____ __            ___
   /  |/  (_)__  (_)_  __/___ _/ /  / ___// /___  ______/ (_)___
  / /|_/ / / _ \\/ / / / / __ `/ /   \\__ \\/ __/ / / / __  / / __ \\
 / /  / / / / / / / / / / /_/ / /   ___/ / /_/ /_/ / /_/ / / /_/ /
/_/  /_/_/_/ /_/_/ /_/  \\__,_/_/   /____/\\__/\\__,_/\\__,_/_/\\____/
{C.RESET}
{C.DIM}  Aspire Orchestrator - Local Development Environment{C.RESET}
{C.DIM}  ===================================================={C.RESET}
""")


def log(tag, color, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{C.DIM}{ts}{C.RESET} {color}{C.BOLD}[{tag}]{C.RESET} {msg}")


def log_system(msg):
    log("SYS", C.WHITE, f"{C.BOLD}{msg}{C.RESET}")


def log_ok(msg):
    log("  +", C.GREEN, msg)


def log_fail(msg):
    log("  !", C.RED, msg)


def log_warn(msg):
    log("  ~", C.YELLOW, msg)


# ?? Pre-flight Checks ???????????????????????????????????????????????????

def check_env_file():
    if not ENV_FILE.exists():
        log_fail(".env file not found at project root")
        log_warn("Copy .env.example to .env and fill in your credentials")
        return False
    log_ok(".env file found")
    return True


def check_python_deps():
    missing = []
    packages = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic_settings": "pydantic-settings",
        "dotenv": "python-dotenv",
        "azure.cosmos": "azure-cosmos",
        "openai": "openai",
        "celery": "celery[redis]",
        "redis": "redis",
        "apscheduler": "apscheduler",
        "moviepy": "moviepy",
        "PIL": "Pillow",
    }
    for mod, pip_name in packages.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)

    if missing:
        log_fail(f"Missing Python packages: {', '.join(missing)}")
        log_warn(f"Run: pip install -r backend/requirements.txt")
        return False
    log_ok(f"Python packages OK ({len(packages)} checked)")
    return True


def check_node_modules():
    nm = FRONTEND_DIR / "node_modules"
    if not nm.exists():
        log_fail("frontend/node_modules not found")
        log_warn("Run: cd frontend && npm install")
        return False
    log_ok("Frontend node_modules present")
    return True


def check_redis():
    try:
        from dotenv import dotenv_values
        env = dotenv_values(ENV_FILE)
        url = env.get("REDIS_URL", "redis://localhost:6379/0")
        import redis as r
        client = r.from_url(url, socket_connect_timeout=5)
        client.ping()
        host = url.split("@")[-1].split("/")[0] if "@" in url else url.split("//")[-1].split("/")[0]
        tls = "TLS" if url.startswith("rediss://") else "plain"
        log_ok(f"Redis connected ({host}, {tls})")
        return True
    except Exception as e:
        log_fail(f"Redis connection failed: {e}")
        return False


def check_cosmos():
    try:
        from dotenv import dotenv_values
        env = dotenv_values(ENV_FILE)
        conn_str = env.get("COSMOS_DB_CONNECTION_STRING", "")
        if not conn_str:
            log_warn("Cosmos DB connection string not set - will run in offline mode")
            return True
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        from azure.cosmos import CosmosClient
        is_emulator = "localhost" in conn_str or "127.0.0.1" in conn_str
        client = CosmosClient.from_connection_string(
            conn_str, connection_verify=False if is_emulator else True
        )
        # Quick connectivity test
        list(client.list_databases())
        label = "Emulator" if is_emulator else "Azure"
        log_ok(f"Cosmos DB connected ({label})")
        return True
    except Exception as e:
        log_fail(f"Cosmos DB connection failed: {e}")
        return False


def check_openai():
    try:
        from dotenv import dotenv_values
        env = dotenv_values(ENV_FILE)
        key = env.get("OPENAI_API_KEY", "")
        if not key:
            log_fail("OPENAI_API_KEY not set in .env")
            return False
        from openai import OpenAI
        client = OpenAI(api_key=key)
        client.models.list()
        log_ok("OpenAI API key valid")
        return True
    except Exception as e:
        log_fail(f"OpenAI API check failed: {e}")
        return False


def check_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def run_preflight():
    log_system("Running pre-flight checks...")
    print()

    checks = [
        ("Environment", check_env_file),
        ("Python Deps", check_python_deps),
        ("Node Modules", check_node_modules),
        ("Redis", check_redis),
        ("Cosmos DB", check_cosmos),
        ("OpenAI", check_openai),
    ]

    results = {}
    for name, fn in checks:
        try:
            results[name] = fn()
        except Exception as e:
            log_fail(f"{name}: unexpected error - {e}")
            results[name] = False

    print()

    # Port checks
    for port, svc in [(8000, "Backend"), (3000, "Frontend")]:
        if not check_port_available(port):
            log_warn(f"Port {port} ({svc}) is already in use - service may fail to bind")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    all_ok = all(results.values())

    print()
    if all_ok:
        log_system(f"Pre-flight: {C.GREEN}{passed}/{total} checks passed{C.RESET}")
    else:
        log_system(f"Pre-flight: {C.YELLOW}{passed}/{total} checks passed{C.RESET}")
        failed = [k for k, v in results.items() if not v]
        log_warn(f"Failed: {', '.join(failed)}")
        print()
        resp = input(f"  {C.YELLOW}Continue anyway? [y/N]: {C.RESET}").strip().lower()
        if resp != "y":
            print(f"\n  {C.DIM}Aborted.{C.RESET}\n")
            sys.exit(1)

    print()
    return all_ok


# ?? Service Management ???????????????????????????????????????????????????

def stream_output(proc, tag, color):
    """Read lines from a process and print them with a colored prefix."""
    try:
        for raw_line in iter(proc.stdout.readline, b""):
            if shutdown_event.is_set():
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if line:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"{C.DIM}{ts}{C.RESET} {color}[{tag}]{C.RESET} {line}")
    except (ValueError, OSError):
        pass  # pipe closed


def _kill_process_tree(pid):
    """Kill a process and all its children (prevents zombie node.exe on Windows)."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    else:
        import signal as sig
        try:
            os.killpg(os.getpgid(pid), sig.SIGTERM)
        except (ProcessLookupError, OSError):
            pass


def start_service(svc):
    """Start a single service as a subprocess."""
    env = os.environ.copy()
    # Ensure .env vars are loaded into the environment
    try:
        from dotenv import dotenv_values
        env.update(dotenv_values(ENV_FILE))
    except ImportError:
        pass

    # React dev server: disable auto-open browser, set port
    if svc["name"] == "Frontend":
        env["BROWSER"] = "none"
        env["PORT"] = "3000"

    try:
        proc = subprocess.Popen(
            svc["cmd"],
            cwd=svc["cwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

        # Start log streaming thread
        t = threading.Thread(
            target=stream_output,
            args=(proc, svc["tag"], svc["color"]),
            daemon=True,
        )
        t.start()

        return proc

    except FileNotFoundError as e:
        log(svc["tag"], C.RED, f"Failed to start: {e}")
        return None


def wait_for_health(url, timeout=30):
    """Poll a URL until it responds 200."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def show_dashboard():
    """Print the service dashboard with URLs."""
    print(f"""
{C.BOLD}{"=" * 60}{C.RESET}
{C.BOLD}{C.CYAN}  MiniTaleStudio - Services Running{C.RESET}
{C.BOLD}{"=" * 60}{C.RESET}

  {C.CYAN}{C.BOLD}Backend API{C.RESET}      http://localhost:8000
  {C.CYAN}{C.BOLD}API Docs{C.RESET}         http://localhost:8000/docs
  {C.MAGENTA}{C.BOLD}Celery Worker{C.RESET}    Connected to Redis
  {C.YELLOW}{C.BOLD}Celery Beat{C.RESET}      Scheduler active
  {C.GREEN}{C.BOLD}Frontend{C.RESET}         http://localhost:3000

{C.BOLD}{"=" * 60}{C.RESET}
  {C.DIM}Press Ctrl+C to stop all services{C.RESET}
{C.BOLD}{"=" * 60}{C.RESET}
""")




def graceful_shutdown(signum=None, frame=None):
    """Stop all running processes and their child trees."""
    if shutdown_event.is_set():
        return
    shutdown_event.set()

    print(f"\n{C.BOLD}{C.YELLOW}")
    print("  Shutting down all services...")
    print(f"{C.RESET}")

    for proc in reversed(processes):
        if proc and proc.poll() is None:
            try:
                _kill_process_tree(proc.pid)
            except (ProcessLookupError, OSError):
                pass

    # Wait up to 5 seconds for graceful exit
    deadline = time.time() + 5
    for proc in processes:
        if proc and proc.poll() is None:
            remaining = max(0, deadline - time.time())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                try:
                    _kill_process_tree(proc.pid)
                except Exception:
                    proc.kill()

    log_system(f"{C.GREEN}All services stopped.{C.RESET}")
    print()


# ?? Main ?????????????????????????????????????????????????????????????????

def main():
    # Enable ANSI colors on Windows
    if sys.platform == "win32":
        os.system("color")

    banner()
    run_preflight()

    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, graceful_shutdown)
    else:
        signal.signal(signal.SIGTERM, graceful_shutdown)

    # Start services in order
    log_system("Starting services...")
    print()

    for svc in SERVICES:
        log(svc["tag"], svc["color"], f"Starting {svc['name']}...")
        proc = start_service(svc)
        if proc:
            processes.append(proc)
            # Small delay between service starts
            time.sleep(2)
        else:
            log(svc["tag"], C.RED, f"Failed to start {svc['name']}")

    # Wait for backend health
    log_system("Waiting for Backend health check...")
    if wait_for_health("http://localhost:8000/", timeout=30):
        log_ok("Backend is healthy")
    else:
        log_warn("Backend health check timed out (may still be starting)")

    # Wait for frontend health
    log_system("Waiting for Frontend health check...")
    if wait_for_health("http://localhost:3000/", timeout=45):
        log_ok("Frontend is healthy")
    else:
        log_warn("Frontend health check timed out (may still be compiling)")

    show_dashboard()

    # Monitor processes
    try:
        while not shutdown_event.is_set():
            for i, (svc, proc) in enumerate(zip(SERVICES, processes)):
                if proc and proc.poll() is not None:
                    exit_code = proc.returncode
                    if not shutdown_event.is_set():
                        log(svc["tag"], C.RED,
                            f"{svc['name']} exited with code {exit_code}")
                        # Restart the service
                        log(svc["tag"], svc["color"],
                            f"Restarting {svc['name']}...")
                        new_proc = start_service(svc)
                        if new_proc:
                            processes[i] = new_proc
                        time.sleep(2)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        graceful_shutdown()


if __name__ == "__main__":
    main()
