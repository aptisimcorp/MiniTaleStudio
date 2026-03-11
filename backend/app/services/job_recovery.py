"""Job recovery service.

On service startup, scans CosmosDB for jobs that have duplicate records
across partitions (e.g. both 'running' and 'completed' docs for the
same job id) and cleans them up.

Jobs genuinely stuck in 'running' or 'queued' (with no completed
counterpart) are marked as 'failed' so the user can retry manually.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Jobs stuck for longer than this are considered orphaned
STUCK_THRESHOLD_MINUTES = 10


def recover_stuck_jobs():
    """Clean up duplicate job records and mark genuinely stuck jobs as failed.

    Because CosmosDB uses ``status`` as the partition key, changing a
    job's status creates a *new* document.  If the delete of the old
    document fails (crash, timeout, deploy) both records survive.

    This function:
    1. Finds every job id that still has a 'running' or 'queued' doc.
    2. If a 'completed' (or 'failed') doc already exists for that id,
       the stale 'running'/'queued' doc is simply deleted.
    3. If no terminal doc exists and the job has been stuck past the
       threshold, it is moved to 'failed' so the user can retry.
    """
    from app.database import cosmos_db

    if not cosmos_db.client:
        cosmos_db.connect()

    # --- Step 1: find all non-terminal job docs ---
    try:
        stale_jobs = cosmos_db.query_items(
            "jobs",
            "SELECT * FROM c WHERE c.status IN ('running', 'queued')",
            [],
        )
    except Exception as e:
        logger.warning("Job recovery: failed to query jobs: %s", e)
        return

    if not stale_jobs:
        logger.info("Job recovery: no stale jobs found")
        return

    # Group by job id (there may be multiple stale docs for the same id)
    stale_by_id: dict[str, list[dict]] = {}
    for job in stale_jobs:
        stale_by_id.setdefault(job["id"], []).append(job)

    cutoff = (datetime.utcnow() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)).isoformat()
    deleted = 0
    failed = 0

    for job_id, docs in stale_by_id.items():
        # --- Step 2: check if a terminal record already exists ---
        terminal = cosmos_db.query_items(
            "jobs",
            "SELECT c.id, c.status FROM c WHERE c.id = @id AND c.status IN ('completed', 'failed')",
            [{"name": "@id", "value": job_id}],
        )

        if terminal:
            # A completed/failed record exists -- the stale docs are leftovers.
            for doc in docs:
                try:
                    cosmos_db.delete_item("jobs", doc["id"], doc["status"])
                    deleted += 1
                    logger.info(
                        "Job recovery: deleted stale '%s' doc for job %s (already %s)",
                        doc["status"], job_id, terminal[0]["status"],
                    )
                except Exception:
                    pass
            continue

        # --- Step 3: no terminal record -- job is genuinely stuck ---
        # Pick the most recently updated doc as the "canonical" one
        canonical = max(docs, key=lambda d: d.get("updated_at", ""))
        updated_at = canonical.get("updated_at", "")

        if updated_at > cutoff:
            logger.debug("Job %s updated recently (%s), skipping", job_id, updated_at)
            continue

        old_status = canonical.get("status", "running")
        old_step = canonical.get("pipeline_step", "unknown")

        logger.info(
            "Job recovery: marking job %s as failed (was '%s' at step '%s' since %s)",
            job_id, old_status, old_step, updated_at,
        )

        # Delete ALL stale docs for this job id
        for doc in docs:
            try:
                cosmos_db.delete_item("jobs", doc["id"], doc["status"])
            except Exception:
                pass

        # Remove Cosmos system properties before re-creating
        for key in ["_rid", "_self", "_etag", "_attachments", "_ts"]:
            canonical.pop(key, None)

        canonical["status"] = "failed"
        canonical["pipeline_step"] = old_step
        canonical["error"] = (
            f"Job was stuck in '{old_status}' at step '{old_step}' "
            f"during a deploy/restart. Use retry to resume."
        )
        canonical["updated_at"] = datetime.utcnow().isoformat()
        cosmos_db.create_item("jobs", canonical)
        failed += 1

    logger.info(
        "Job recovery: deleted %d stale duplicate(s), marked %d stuck job(s) as failed",
        deleted, failed,
    )
