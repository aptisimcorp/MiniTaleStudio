# MiniTaleStudio

AI Short Video Generation Platform – Automatically generates vertical storytelling videos for YouTube Shorts, Instagram Reels, and TikTok.

## Features

- **Frontend Dashboard** – Configure story generation, scheduling, and monitor jobs.
- **Backend APIs** – FastAPI-powered REST endpoints for configurations, video generation, and job management.
- **AI Pipeline** – OpenAI-powered story generation, image creation, TTS narration, and subtitle generation.
- **Video Assembly** – MoviePy/FFmpeg-based video composition with images, narration, subtitles, and optional music.
- **Background Processing** – Celery workers with Redis for async video generation.
- **Scheduling** – Celery Beat for recurring video generation jobs.
- **Database** – Azure Cosmos DB for storing configurations, schedules, and job results.
- **Multi-language** – English and Hindi support.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TailwindCSS |
| Backend | Python, FastAPI |
| Background Processing | Celery, Redis |
| Database | Azure Cosmos DB (NoSQL) |
| AI Services | OpenAI API |
| Video Processing | MoviePy, FFmpeg |

## Project Structure

```
MiniTaleStudio/
??? backend/                  # FastAPI backend
?   ??? app/
?   ?   ??? main.py           # Application entry point
?   ?   ??? config.py         # Environment settings
?   ?   ??? database.py       # Cosmos DB client
?   ?   ??? models.py         # Pydantic schemas
?   ?   ??? routes/           # API endpoints
?   ?   ??? services/         # AI pipeline services
?   ?   ??? workers/          # Celery tasks
?   ?   ??? scheduler/        # Job scheduling
?   ??? requirements.txt
?   ??? Dockerfile
??? frontend/                 # React dashboard
?   ??? public/
?   ??? src/
?   ?   ??? api/              # API client
?   ?   ??? components/       # UI components
?   ?   ??? pages/            # Page layouts
?   ??? package.json
?   ??? Dockerfile
??? assets/                   # Generated assets
?   ??? images/
?   ??? audio/
?   ??? subtitles/
??? output/                   # Final videos
?   ??? videos/
??? docker-compose.yml
??? aspire.py                 # Aspire orchestrator (single launch)
??? Procfile                  # Honcho/Foreman process file
??? .env.example
??? README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- FFmpeg (bundled via imageio_ffmpeg)
- Azure Cosmos DB account (or [local Emulator](https://learn.microsoft.com/en-us/azure/cosmos-db/local-emulator))
- OpenAI API key
- Redis (local or [Upstash](https://upstash.com/))

### 1. Clone and configure

```bash
git clone https://github.com/aptisimcorp/MiniTaleStudio.git
cd MiniTaleStudio
cp .env.example .env
# Edit .env with your API keys and connection strings
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

### 3. Launch everything (Aspire Orchestrator)

**One command to start all services:**

```bash
python aspire.py
```

This runs pre-flight checks (env, packages, Redis, Cosmos DB, OpenAI) and then starts:

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Celery Worker | (connected to Redis) |
| Celery Beat | (scheduler) |
| Frontend Dashboard | http://localhost:3000 |

Press `Ctrl+C` to gracefully stop all services.

### Alternative: Manual startup (4 terminals)

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Celery Worker:**
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

**Terminal 3 - Celery Beat:**
```bash
cd backend
celery -A app.workers.celery_app beat --loglevel=info
```

**Terminal 4 - Frontend:**
```bash
cd frontend
npm start
```

### Alternative: Procfile (honcho)

```bash
pip install honcho
honcho start
```

### Alternative: Docker Compose

```bash
docker-compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/configurations` | Save video generation configuration |
| POST | `/generate-video` | Trigger immediate video generation |
| POST | `/schedule-job` | Create a scheduled generation job |
| GET | `/jobs` | List all jobs with status |
| GET | `/videos` | List all generated videos |

## Video Specifications

| Setting | Value |
|---------|-------|
| Resolution | 1080×1920 (vertical) |
| FPS | 24 |
| Duration | 60–90s, 90–120s, or 120–180s |
| Scenes | 6–8 (short), 8–10 (medium), 10–12 (long) |
| Output | `output/videos/story_<timestamp>.mp4` |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `COSMOS_DB_CONNECTION_STRING` | Azure Cosmos DB connection string |
| `COSMOS_DB_DATABASE_NAME` | Cosmos DB database name |
| `REDIS_URL` | Redis connection URL |

## License

MIT
