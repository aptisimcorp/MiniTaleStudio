import uuid
from datetime import datetime

from fastapi import APIRouter

from app.database import cosmos_db
from app.models import ScheduleCreate, ScheduleResponse

router = APIRouter()


@router.post("/schedule-job", response_model=ScheduleResponse)
async def schedule_job(schedule: ScheduleCreate):
    from app.scheduler.scheduler import add_schedule

    item = schedule.model_dump()
    item["id"] = str(uuid.uuid4())
    item["created_at"] = datetime.utcnow().isoformat()
    saved = cosmos_db.create_item("schedules", item)

    add_schedule(saved)

    return ScheduleResponse(**saved)


@router.get("/schedules")
async def list_schedules():
    items = cosmos_db.query_items("schedules", "SELECT * FROM c ORDER BY c._ts DESC")
    return items


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    from app.scheduler.scheduler import remove_schedule

    items = cosmos_db.query_items(
        "schedules",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": schedule_id}],
    )
    if items:
        item = items[0]
        cosmos_db.delete_item("schedules", schedule_id, item.get("schedule_type", ""))
        remove_schedule(schedule_id)
    return {"message": "Schedule removed"}
