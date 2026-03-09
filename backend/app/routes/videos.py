import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from app.auth import get_current_user
from app.database import cosmos_db
from app.models import GenerateVideoRequest, JobStatus, PipelineStep

router = APIRouter()





@router.post("/generate-video")
async def generate_video(request: GenerateVideoRequest, user: dict = Depends(get_current_user)):
    from app.workers.tasks import run_video_pipeline

    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    user_id = user["user_id"]

    config_dict = request.model_dump()

    job_item = {
        "id": job_id,
        "user_id": user_id,
        "configuration_id": request.configuration_id or "",
        "status": JobStatus.QUEUED.value,
        "pipeline_step": PipelineStep.QUEUED.value,
        "category": request.category.value,
        "language": request.language.value,
        "duration": request.duration.value,
        "ai_service": request.ai_service.value,
        "character_style": request.character_style.value,
        "characters": request.characters,
        "title": "",
        "script": "",
        "video_path": None,
        "blob_url": None,
        "total_cost": 0.0,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "config_dict": config_dict,
    }
    cosmos_db.create_item("jobs", job_item)

    run_video_pipeline.delay(job_id, config_dict, user_id)

    return {"job_id": job_id, "status": "queued", "message": "Video generation started."}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, user: dict = Depends(get_current_user)):
    """Retry a failed or crashed job. Resumes from the last checkpoint if available."""
    from app.workers.tasks import run_video_pipeline

    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": job_id}],
    )
    if not items:
        raise HTTPException(status_code=404, detail="Job not found")

    job = items[0]
    if job.get("status") == JobStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Job already completed")

    user_id = user["user_id"]

    # Recover the full config that was saved at job creation time.
    # Fall back to reconstructing from individual job fields so older
    # jobs (created before config_dict was persisted) still work.
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

    run_video_pipeline.delay(job_id, config_dict, user_id)

    return {"job_id": job_id, "status": "retrying", "message": "Job retry started. Will resume from last checkpoint."}


@router.get("/videos")
async def list_videos(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.status = 'completed' AND c.video_path != null AND c.user_id = @uid ORDER BY c._ts DESC",
        [{"name": "@uid", "value": user_id}],
    )
    # Deduplicate by job id
    seen = set()
    items = [i for i in items if i["id"] not in seen and not seen.add(i["id"])]
    videos = []
    for item in items:
        raw_path = item.get("blob_url") or item.get("video_path") or ""
        filename = os.path.basename(raw_path) if raw_path else ""
        videos.append({
            "id": item["id"],
            "job_id": item["id"],
            "user_id": item.get("user_id", ""),
            "filename": filename,
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "language": item.get("language", ""),
            "duration": item.get("duration", ""),
            "ai_service": item.get("ai_service", "openai"),
            "character_style": item.get("character_style", ""),
            "characters": item.get("characters", []),
            "total_cost": item.get("total_cost", 0.0),
            "thumbnail": None,
            "file_path": filename,
            "blob_url": item.get("blob_url", ""),
            "youtube_url": item.get("youtube_url", ""),
            "youtube_video_id": item.get("youtube_video_id", ""),
            "youtube_uploaded_at": item.get("youtube_uploaded_at", ""),
            "created_at": item.get("created_at", ""),
        })
    return videos
