from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models import ScheduleType

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def _trigger_generation(configuration_id: str):
    from app.database import cosmos_db
    from app.workers.tasks import run_video_pipeline
    import uuid
    from datetime import datetime

    items = cosmos_db.query_items(
        "configurations",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": configuration_id}],
    )
    if not items:
        print(f"[Scheduler] Configuration {configuration_id} not found, skipping.")
        return

    config = items[0]
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    job_item = {
        "id": job_id,
        "configuration_id": configuration_id,
        "status": "queued",
        "category": config.get("category", ""),
        "language": config.get("language", ""),
        "duration": config.get("duration", ""),
        "video_path": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    cosmos_db.create_item("jobs", job_item)

    run_video_pipeline.delay(job_id, config)
    print(f"[Scheduler] Triggered job {job_id} for config {configuration_id}")


def add_schedule(schedule: dict):
    scheduler = get_scheduler()
    schedule_id = schedule["id"]
    config_id = schedule["configuration_id"]
    schedule_type = schedule["schedule_type"]
    cron_expr = schedule.get("cron_expression")

    if schedule_type == ScheduleType.HOURLY.value:
        trigger = IntervalTrigger(hours=1)
    elif schedule_type == ScheduleType.DAILY.value:
        trigger = IntervalTrigger(days=1)
    elif schedule_type == ScheduleType.WEEKLY.value:
        trigger = IntervalTrigger(weeks=1)
    elif schedule_type == ScheduleType.CRON.value and cron_expr:
        parts = cron_expr.strip().split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
        )
    else:
        trigger = IntervalTrigger(days=1)

    scheduler.add_job(
        _trigger_generation,
        trigger=trigger,
        args=[config_id],
        id=schedule_id,
        replace_existing=True,
    )
    print(f"[Scheduler] Added schedule {schedule_id} ({schedule_type})")


def remove_schedule(schedule_id: str):
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(schedule_id)
        print(f"[Scheduler] Removed schedule {schedule_id}")
    except Exception:
        pass


def load_schedules_from_db():
    from app.database import cosmos_db

    schedules = cosmos_db.query_items(
        "schedules",
        "SELECT * FROM c WHERE c.enabled = true",
    )
    for schedule in schedules:
        add_schedule(schedule)
    print(f"[Scheduler] Loaded {len(schedules)} schedules from DB")
