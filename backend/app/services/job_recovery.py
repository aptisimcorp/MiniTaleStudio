"""Job recovery service.

On service startup, scans CosmosDB for jobs stuck in 'running' status
(from a prior crash) and re-queues them so they resume from their
last checkpoint.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Jobs stuck in 'running' for longer than this are considered orphaned
STUCK_THRESHOLD_MINUTES = 10


def recover_stuck_jobs():
    """Find jobs stuck in 'running' status and re-queue them via Celery.

    Called once during FastAPI startup. Each recovered job will
    automatically resume from its last disk checkpoint, skipping
    already-completed pipeline steps.
    """
    from app.database import cosmos_db
    from app.workers.tasks import run_video_pipeline

    if not cosmos_db.client:
        cosmos_db.connect()

    try:
        stuck_jobs = cosmos_db.query_items(
            "jobs",
            "SELECT * FROM c WHERE c.status = 'running'",
            [],
        )
    except Exception as e:
        logger.warning("Job recovery: failed to query stuck jobs: %s", e)
        return

    if not stuck_jobs:
        logger.info("Job recovery: no stuck jobs found")
        return

    cutoff = (datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)).isoformat()
    recovered = 0

    for job in stuck_jobs:
        # Only recover jobs that have been stuck past the threshold
        updated_at = job.get("updated_at", "")
        if updated_at > cutoff:
            logger.debug("Job %s updated recently (%s), skipping", job["id"], updated_at)
            continue

        job_id = job["id"]
        user_id = job.get("user_id", "admin_user")

        # Recover the full config (same logic as the retry endpoint)
        config_dict = job.get("config_dict")
        if not config_dict:
            config_dict = {
                "category": job.get("category", "horror"),
                "language": job.get("language", "english"),
                "duration": job.get("duration", "60-90"),
                "configuration_id": job.get("configuration_id", ""),
                "ai_service": job.get("ai_service", "openai"),
                "character_style": job.get("character_style", "realistic"),
                "characters": job.get("characters", []),
                "voice_type": job.get("voice_type", "alloy"),
                "background_music": job.get("background_music", False),
                "subtitle_style": job.get("subtitle_style", "default"),
                "image_style": job.get("image_style", "photo_realism"),
                "watermark_path": job.get("watermark_path"),
                "splash_start_path": job.get("splash_start_path"),
                "splash_end_path": job.get("splash_end_path"),
            }

        logger.info(
            "Job recovery: re-queuing job %s (stuck since %s, ai_service=%s)",
            job_id, updated_at, config_dict.get("ai_service", "openai"),
        )
        run_video_pipeline.delay(job_id, config_dict, user_id)
        recovered += 1

    logger.info("Job recovery: re-queued %d stuck job(s)", recovered)
