
# MiniTale Studio – System Modification Guide

This document describes incremental changes required to enhance the existing running system.

Current system already includes:
- FastAPI backend
- React dashboard
- Azure Cosmos DB
- Azure Blob Storage
- OpenAI integration
- Video generation pipeline
- YouTube API credentials
- Environment variables configured

Goal:
Add authentication, user-based isolation, Azure Blob storage enforcement, cleanup jobs, and YouTube uploads without rebuilding the system.

---

# 1 Authentication (Admin Login)

Add a login system so the application cannot be accessed without authentication.

Create a login page in React with:

- Email
- Password
- Login button

API:

POST /auth/login

Request:

{
  "email": "string",
  "password": "string"
}

Response:

{
  "access_token": "jwt_token",
  "token_type": "bearer"
}

Use JWT authentication.

Token expiry: 24 hours.

---

# 2 Cosmos DB Users Collection

Create a collection:

users

Insert a default admin user during backend startup.

Admin credentials:

Email:
minitalestudio75@gmail.com

Password:
Admin@1949

Password must be encrypted using bcrypt.

Example document:

{
"id": "admin_user",
"email": "minitalestudio75@gmail.com",
"password_hash": "<bcrypt_hash>",
"role": "admin",
"created_at": "timestamp"
}

---

# 3 Backend Authentication Middleware

Create JWT validation middleware in FastAPI.

All APIs must require authentication except:

/auth/login
/docs
/openapi.json

Protected endpoints:

/generate-video
/videos
/jobs
/configurations
/youtube/upload

JWT payload:

{
"user_id": "",
"email": "",
"role": "admin"
}

---

# 4 User Based Data Model

Add user_id field to:

videos collection
jobs collection
configurations collection

Example video document:

{
"id": "video_id",
"user_id": "admin_user",
"title": "Generated Video",
"category": "horror",
"language": "english",
"blob_url": "https://storageminitalestudio.blob.core.windows.net/minitalestudio/video123.mp4",
"created_at": "timestamp"
}

All queries must filter by user_id.

---

# 5 Azure Blob Storage Enforcement

All generated videos must be stored in Azure Blob Storage.

Container name:

minitalestudio

Use environment variable:

AZURE_STORAGE_CONNECTION_STRING

Upload flow:

1 Generate video locally
2 Upload to Azure Blob Storage
3 Save blob URL in Cosmos DB
4 Delete local video

Example blob URL:

https://storageminitalestudio.blob.core.windows.net/minitalestudio/video123.mp4

---

# 6 Temporary Image Handling

During video generation images are stored temporarily.

Example folder:

jobs/job_20260307_12345/

Images are only needed for assembling the video.

After video creation delete all generated images.

---

# 7 Cleanup Job

Create background cleanup service.

Run every 30 minutes.

Steps:

1 Scan jobs directory
2 Identify folders older than 30 minutes
3 Delete folders if processing completed or failed

Example folders:

jobs/job_12345/
jobs/job_67890/

Use:

APScheduler or Celery worker.

---

# 8 YouTube Upload Feature

Add endpoint:

POST /youtube/upload

Request:

{
"video_id": "string"
}

Flow:

1 Retrieve video metadata from Cosmos DB
2 Get Blob Storage URL
3 Download video temporarily
4 Upload video using YouTube Data API v3
5 Save upload metadata

Example response:

{
"youtube_video_id": "abc123",
"youtube_url": "https://youtube.com/watch?v=abc123"
}

---

# 9 Store YouTube Tokens Per User

Create collection:

youtube_accounts

Example document:

{
"user_id": "admin_user",
"access_token": "...",
"refresh_token": "...",
"expires_at": "timestamp",
"connected_at": "timestamp"
}

Refresh tokens must be used for automatic uploads.

---

# 10 Frontend Changes

Add login page.

After login store JWT token in local storage.

All API calls must include:

Authorization: Bearer <jwt_token>

Dashboard must display user specific data.

Add button in video cards:

Upload to YouTube

Video cards should show:

thumbnail
category
language
duration
created date
play button
upload button

---

# 11 Video Generation Pipeline Update

Update pipeline:

Generate story
Generate images
Generate narration
Create video
Upload video to Azure Blob
Delete temporary images
Save metadata in Cosmos DB

---

# 12 Security

Use:

bcrypt for password hashing
JWT authentication
secure environment variables

Never store plain text passwords.

---

# 13 Environment Variables

Already configured:

OPENAI_API_KEY
COSMOS_DB_CONNECTION_STRING
AZURE_STORAGE_CONNECTION_STRING
YOUTUBE_CLIENT_ID
YOUTUBE_CLIENT_SECRET
JWT_SECRET_KEY

No new variables required.

---

# 14 Expected Result

After modifications:

User must login before accessing dashboard.

Admin credentials:

Email:
minitalestudio75@gmail.com

Password:
Admin@1949

After login user can:

- generate videos
- view videos
- upload videos to YouTube

All generated media stored in Azure Blob.

Temporary files automatically cleaned.

User data isolated by user_id.
