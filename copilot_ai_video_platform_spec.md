
# AI Short Video Generation Platform – Copilot Agent Specification

## Goal
Build a full-stack AI system that automatically generates vertical storytelling videos for YouTube Shorts, Instagram Reels, and TikTok.

The system must include:
- Frontend dashboard
- Backend APIs
- Background workers
- Scheduling
- AI video generation pipeline
- Configuration stored in Azure Cosmos DB
- Support for English and Hindi videos
- Integration with OpenAI APIs for script generation, image generation, and TTS

Final videos must be saved locally so they can later be uploaded using social media APIs.

---

# Technology Stack

Frontend
- React
- TailwindCSS

Backend
- Python
- FastAPI

Background Processing
- Celery
- Redis

Database
- Azure Cosmos DB (NoSQL)

AI Services
- OpenAI API

Video Processing
- MoviePy
- FFmpeg

---

# Video Requirements

Format: Vertical

Resolution: 1080x1920  
FPS: 24  

Duration Options
- 60–90 seconds
- 90–120 seconds
- 120–180 seconds

Scenes
- Short: 6–8 scenes
- Medium: 8–10 scenes
- Long: 10–12 scenes

Output Location
output/videos/story_<timestamp>.mp4

---

# Frontend Dashboard

Create a configuration dashboard where users can configure generation settings.

## User Inputs

Story Category
- Horror
- Funny
- Crime
- Thriller
- History
- Mystery
- Adult
- Custom

Language
- English
- Hindi

Video Duration
- 60–90 seconds
- 90–120 seconds
- 120–180 seconds

Generation Mode
- Run instantly
- Schedule

Schedule Options
- hourly
- daily
- weekly
- cron expression

Additional Settings
- number of videos
- voice type
- background music toggle
- subtitle style
- image style (cinematic / cartoon / realistic)

---

# Dashboard Components

Configuration Panel  
Generate Now Button  
Scheduler Settings  
Job Progress Monitor  
Job History  
Generated Video Gallery  

Each video card should show:

- Thumbnail
- Category
- Language
- Duration
- Timestamp
- Download Button

---

# Database (Azure Cosmos DB)

Use Cosmos DB to store configurations, schedules, and job results.

Collections:

configurations  
schedules  
jobs

---

# Backend APIs

POST /configurations  
POST /generate-video  
POST /schedule-job  
GET /jobs  
GET /videos  

---

# Video Generation Pipeline

Each job should execute:

1. Generate Story (OpenAI API)
2. Split into Scenes
3. Generate Images
4. Generate Narration
5. Generate Subtitles
6. Assemble Video

---

# Story Generation

Word length based on duration.

60–90 sec → 150–180 words  
90–120 sec → 200–240 words  
120–180 sec → 260–350 words

Structure:

Hook → Setup → Rising tension → Climax → Twist ending

Language must follow user selection (Hindi or English).

---

# Image Generation

Use OpenAI image generation.

Requirements:

- cinematic lighting
- vertical framing
- consistent style

Save images to:

assets/images/

---

# Narration

Use OpenAI TTS.

Voice language must match selected language.

Save audio to:

assets/audio/narration.mp3

---

# Subtitles

Auto-generate subtitles.

Save:

assets/subtitles/story.srt

---

# Video Assembly

Use MoviePy or FFmpeg.

Combine:

- images
- narration
- subtitles
- optional music

Export:

output/videos/story_timestamp.mp4

---

# Background Processing

Use Celery Workers.

Queue: Redis

States:

queued  
running  
completed  
failed

---

# Scheduler

Use Celery Beat or APScheduler.

Scheduler reads configuration from Cosmos DB.

Examples:

Generate horror video daily.  
Generate funny videos every 6 hours.

---

# Project Structure

project/

backend/  
frontend/  
assets/  
output/  

---

# Environment Variables

OPENAI_API_KEY  
COSMOS_DB_CONNECTION_STRING  
REDIS_URL  

Support .env.

---

# Expected Result

A full platform that allows users to configure story generation from a web dashboard and automatically generate short videos using OpenAI APIs while storing configuration and schedules in Azure Cosmos DB.
