import os
import ssl
from dotenv import load_dotenv
from celery import Celery
from celery.signals import worker_ready

# Ensure .env is loaded before importing settings (Celery workers may
# start from a different working directory than the project root).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from app.config import settings

celery_app = Celery(
    "minitale_studio",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# TLS configuration for Upstash Redis (rediss:// scheme)
_redis_uses_tls = settings.redis_url.startswith("rediss://")

_ssl_conf = {
    "ssl_cert_reqs": ssl.CERT_NONE,
} if _redis_uses_tls else {}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # If a worker is killed mid-task, Redis will re-deliver the unacked
    # message after this timeout so another worker can pick it up.
    broker_transport_options={"visibility_timeout": 600},  # 10 minutes
    # Upstash Redis TLS settings
    broker_use_ssl=_ssl_conf if _redis_uses_tls else None,
    redis_backend_use_ssl=_ssl_conf if _redis_uses_tls else None,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])


# ?? APScheduler lives in the worker process (not the web server) ??????
# The web server on Render sleeps after inactivity, killing any in-memory
# scheduler. The Celery worker stays alive as a background service, so
# APScheduler runs here reliably.

@worker_ready.connect
def _on_worker_ready(**kwargs):
    """Load all enabled schedules from Cosmos DB when the worker starts."""
    try:
        from app.scheduler.scheduler import load_schedules_from_db
        load_schedules_from_db()
    except Exception as e:
        print(f"[Worker] Schedule loading failed (non-fatal): {e}")


@celery_app.task(name="app.workers.celery_app.reload_schedules")
def reload_schedules():
    """Reload all schedules from DB into the worker's APScheduler.

    Called via .delay() from the web API when a schedule is created or deleted,
    so the worker picks up changes without a restart.
    """
    try:
        from app.scheduler.scheduler import load_schedules_from_db
        load_schedules_from_db()
    except Exception as e:
        print(f"[Worker] Schedule reload failed: {e}")
