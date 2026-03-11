from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models import ScheduleType

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    return _scheduler


def _trigger_generation(configuration_id: str):
    from app.database import cosmos_db
    from app.workers.tasks import run_video_pipeline
    from app.models import JobStatus, PipelineStep
    import uuid
    from datetime import datetime

    if not cosmos_db.client:
        cosmos_db.connect()

    items = cosmos_db.query_items(
        "configurations",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": configuration_id}],
    )
    if not items:
        print(f"[Scheduler] Configuration {configuration_id} not found, skipping.")
        return

    config_doc = items[0]
    user_id = config_doc.get("user_id", "admin_user")
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Build a clean config dict that matches ConfigurationCreate fields.
    # Strip Cosmos metadata keys so Pydantic validation won't reject them.
    _cosmos_keys = {"_rid", "_self", "_etag", "_attachments", "_ts", "id", "user_id", "created_at"}
    config_dict = {k: v for k, v in config_doc.items() if k not in _cosmos_keys}

    job_item = {
        "id": job_id,
        "user_id": user_id,
        "configuration_id": configuration_id,
        "status": JobStatus.QUEUED.value,
        "pipeline_step": PipelineStep.QUEUED.value,
        "category": config_doc.get("category", ""),
        "language": config_doc.get("language", ""),
        "duration": config_doc.get("duration", ""),
        "ai_service": config_doc.get("ai_service", "openai"),
        "character_style": config_doc.get("character_style", ""),
        "characters": config_doc.get("characters", []),
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
    print(f"[Scheduler] Triggered job {job_id} for config {configuration_id} (user={user_id})")


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
            timezone="UTC",
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

    if not cosmos_db.client:
        cosmos_db.connect()

    schedules = cosmos_db.query_items(
        "schedules",
        "SELECT * FROM c WHERE c.enabled = true",
    )
    for schedule in schedules:
        try:
            add_schedule(schedule)
        except Exception as e:
            print(f"[Scheduler] Failed to load schedule {schedule.get('id')}: {e}")
    print(f"[Scheduler] Loaded {len(schedules)} schedules from DB")
