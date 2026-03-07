from fastapi import APIRouter, Depends

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
