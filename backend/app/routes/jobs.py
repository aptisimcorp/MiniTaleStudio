from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import cosmos_db

router = APIRouter()


@router.get("/jobs")
async def list_jobs(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.user_id = @uid ORDER BY c._ts DESC",
        [{"name": "@uid", "value": user_id}],
    )
    # Deduplicate: keep only the latest entry per job id
    seen = set()
    unique = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)
    return unique


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": job_id}],
    )
    if not items:
        return {"error": "Job not found"}
    return items[0]


@router.post("/jobs/{job_id}/retry-upload")
async def retry_upload(job_id: str, user: dict = Depends(get_current_user)):
    """Retry blob upload for a specific job whose video exists locally but wasn't uploaded."""
    from app.workers.tasks import retry_blob_upload

    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": job_id}],
    )
    if not items:
        raise HTTPException(status_code=404, detail="Job not found")

    job = items[0]
    blob_url = job.get("blob_url", "")
    if blob_url and blob_url.startswith("http"):
        return {"job_id": job_id, "status": "skipped", "message": "Already uploaded", "blob_url": blob_url}

    retry_blob_upload.delay(job_id)
    return {"job_id": job_id, "status": "queued", "message": "Blob re-upload queued on worker."}


@router.post("/jobs/retry-all-uploads")
async def retry_all_uploads(user: dict = Depends(get_current_user)):
    """Find all completed jobs with local blob_url and queue re-uploads."""
    from app.workers.tasks import retry_blob_upload

    items = cosmos_db.query_items(
        "jobs",
        "SELECT c.id, c.blob_url, c.video_path FROM c WHERE c.status = 'completed'",
        [],
    )

    queued = []
    skipped = []
    for job in items:
        blob_url = job.get("blob_url", "") or ""
        if blob_url.startswith("http"):
            skipped.append(job["id"])
            continue
        retry_blob_upload.delay(job["id"])
        queued.append(job["id"])

    return {
        "queued": len(queued),
        "skipped": len(skipped),
        "queued_job_ids": queued,
        "message": f"Queued {len(queued)} job(s) for blob re-upload.",
    }
