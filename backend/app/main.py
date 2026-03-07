import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import cosmos_db
from app.routes import configurations, videos, jobs, scheduler
from app.routes import auth as auth_route
from app.routes import youtube as youtube_route
from app.routes.auth import seed_admin_user
from app.services.blob_storage import ensure_container_exists

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


def _start_cleanup_scheduler():
    """Start APScheduler background job to clean up old job folders every 30 minutes."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.services.cleanup import cleanup_old_job_folders

        scheduler_instance = BackgroundScheduler()
        scheduler_instance.add_job(cleanup_old_job_folders, "interval", minutes=30, id="cleanup_job_folders")
        scheduler_instance.start()
        print("[Cleanup] Background cleanup scheduler started (every 30 min).")
    except Exception as e:
        print(f"[Cleanup] Failed to start cleanup scheduler: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cosmos_db.connect()
    os.makedirs(os.path.join(settings.assets_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(settings.assets_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(settings.assets_dir, "subtitles"), exist_ok=True)
    os.makedirs(os.path.join(settings.output_dir, "videos"), exist_ok=True)
    os.makedirs(settings.jobs_dir, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Seed default admin user
    seed_admin_user()

    # Ensure Azure Blob container exists
    ensure_container_exists()

    # Start cleanup scheduler
    _start_cleanup_scheduler()

    yield


app = FastAPI(
    title="MiniTaleStudio API",
    description="AI Short Video Generation Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir(settings.output_dir):
    app.mount("/static/videos", StaticFiles(directory=os.path.join(settings.output_dir, "videos")), name="videos")

# Public routes (no auth required)
app.include_router(auth_route.router, tags=["Authentication"])

# Protected routes (auth required via Depends in each route)
app.include_router(configurations.router, tags=["Configurations"])
app.include_router(videos.router, tags=["Videos"])
app.include_router(jobs.router, tags=["Jobs"])
app.include_router(scheduler.router, tags=["Scheduler"])
app.include_router(youtube_route.router, tags=["YouTube"])


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "MiniTaleStudio API"}


@app.post("/upload", tags=["Upload"])
async def upload_file(file: UploadFile = File(...)):
    """Upload a watermark or splash screen image. Returns the server-side path."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    data = await file.read()
    with open(save_path, "wb") as f:
        f.write(data)
    return {"filename": unique_name, "path": save_path}
