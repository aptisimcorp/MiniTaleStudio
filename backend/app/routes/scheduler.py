import uuid
from datetime import datetime

from fastapi import APIRouter

from app.database import cosmos_db
from app.models import ScheduleCreate, ScheduleResponse

router = APIRouter()


@router.post("/schedule-job", response_model=ScheduleResponse)
async def schedule_job(schedule: ScheduleCreate):
    item = schedule.model_dump()
    item["id"] = str(uuid.uuid4())
    item["created_at"] = datetime.utcnow().isoformat()
    saved = cosmos_db.create_item("schedules", item)

    # Signal the Celery worker to reload schedules (APScheduler runs there)
    from app.workers.celery_app import reload_schedules
    reload_schedules.delay()

    return ScheduleResponse(**saved)


@router.get("/schedules")
async def list_schedules():
    items = cosmos_db.query_items("schedules", "SELECT * FROM c ORDER BY c._ts DESC")
    return items


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    items = cosmos_db.query_items(
        "schedules",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": schedule_id}],
    )
    if items:
        item = items[0]
        cosmos_db.delete_item("schedules", schedule_id, item.get("schedule_type", ""))

    # Signal the Celery worker to reload schedules (removes deleted ones)
    from app.workers.celery_app import reload_schedules
    reload_schedules.delay()

    return {"message": "Schedule removed"}
