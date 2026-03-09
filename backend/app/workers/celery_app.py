import os
import ssl
from dotenv import load_dotenv
from celery import Celery

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
