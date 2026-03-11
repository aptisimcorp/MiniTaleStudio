import os
import tempfile
import uuid
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.auth import get_current_user
from app.config import settings
from app.database import cosmos_db
from app.models import YouTubeUploadRequest, YouTubeUploadResponse
from app.services.youtube_uploader import _build_viral_title, _build_viral_description, _build_viral_tags

router = APIRouter()

# YouTube OAuth2 scopes required for uploading videos
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ---------------------------------------------------------------------------
# OAuth Connect / Callback
# ---------------------------------------------------------------------------

@router.get("/youtube/connect")
async def youtube_connect(user: dict = Depends(get_current_user)):
    """Return the Google OAuth2 consent URL. The frontend should redirect the
    user's browser to this URL so they can authorize YouTube access."""
    if not settings.youtube_client_id:
        raise HTTPException(status_code=500, detail="YOUTUBE_CLIENT_ID is not configured")

    params = {
        "client_id": settings.youtube_client_id,
        "redirect_uri": settings.youtube_redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": user["user_id"],  # pass user_id so callback can associate tokens
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    auth_url = f"{GOOGLE_AUTH_URL}?{query}"
    return {"auth_url": auth_url}


@router.get("/oauth/callback")
async def oauth_callback(code: str = Query(...), state: str = Query(default="admin_user")):
    """Google redirects here after the user authorises YouTube access.
    Exchange the authorization code for access + refresh tokens and store them."""
    if not cosmos_db.client:
        cosmos_db.connect()

    user_id = state  # the user_id we passed in the 'state' param

    # Exchange auth code for tokens
    token_response = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.youtube_client_id,
        "client_secret": settings.youtube_client_secret,
        "redirect_uri": settings.youtube_redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)

    if token_response.status_code != 200:
        return HTMLResponse(
            content="<h2>YouTube connection failed</h2>"
                    f"<p>Google returned: {token_response.text}</p>"
                    "<p>You can close this window and try again.</p>",
            status_code=400,
        )

    token_data = token_response.json()

    # Upsert the youtube_accounts document for this user
    now = datetime.utcnow().isoformat()
    expires_in = token_data.get("expires_in", 3600)

    account_doc = {
        "id": f"yt_{user_id}",
        "user_id": user_id,
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
        "connected_at": now,
    }
    cosmos_db.upsert_item("youtube_accounts", account_doc)
    print(f"[YouTube] OAuth tokens saved for user {user_id}")

    # Return a simple HTML page that auto-closes / redirects back to the app
    return HTMLResponse(
        content="""
        <html>
        <head><title>YouTube Connected</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:60px;">
            <h2 style="color:#22c55e;">YouTube account connected successfully!</h2>
            <p>You can close this window and return to MiniTaleStudio.</p>
            <script>
                setTimeout(function(){ window.close(); }, 3000);
            </script>
        </body>
        </html>
        """,
        status_code=200,
    )


@router.get("/youtube/status")
async def youtube_status(user: dict = Depends(get_current_user)):
    """Check whether the current user has a connected YouTube account."""
    user_id = user["user_id"]
    accounts = cosmos_db.query_items(
        "youtube_accounts",
        "SELECT * FROM c WHERE c.user_id = @uid",
        [{"name": "@uid", "value": user_id}],
    )
    if accounts:
        account = accounts[0]
        return {
            "connected": True,
            "connected_at": account.get("connected_at"),
            "expires_at": account.get("expires_at"),
        }
    return {"connected": False}


# ---------------------------------------------------------------------------
# Helper: build authenticated YouTube API service
# ---------------------------------------------------------------------------

def _get_youtube_service(user_id: str):
    """Build an authenticated YouTube Data API v3 service for the given user."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    accounts = cosmos_db.query_items(
        "youtube_accounts",
        "SELECT * FROM c WHERE c.user_id = @uid",
        [{"name": "@uid", "value": user_id}],
    )
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="No YouTube account connected. Please link your YouTube account first.",
        )

    account = accounts[0]
    creds = Credentials(
        token=account.get("access_token"),
        refresh_token=account.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
    )

    # If the token is expired, the google-auth library will auto-refresh it
    # using the refresh_token. Persist the refreshed token back to Cosmos.
    service = build("youtube", "v3", credentials=creds)

    if creds.token != account.get("access_token"):
        account["access_token"] = creds.token
        account["expires_at"] = creds.expiry.isoformat() if creds.expiry else account.get("expires_at")
        cosmos_db.upsert_item("youtube_accounts", account)

    return service


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/youtube/upload", response_model=YouTubeUploadResponse)
async def youtube_upload(request: YouTubeUploadRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]

    # 1. Retrieve video metadata from Cosmos DB
    videos = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.id = @vid AND c.status = 'completed'",
        [{"name": "@vid", "value": request.video_id}],
    )
    if not videos:
        raise HTTPException(status_code=404, detail="Video not found or not completed")

    video = videos[0]
    blob_url = video.get("blob_url") or ""
    video_path = video.get("video_path") or ""

    # Determine the best source for the video file
    source_url = None
    if blob_url and blob_url.startswith("http"):
        source_url = blob_url
    elif video_path and video_path.startswith("http"):
        source_url = video_path
    elif video_path and os.path.exists(video_path):
        source_url = video_path  # local file
    elif blob_url and os.path.exists(blob_url):
        source_url = blob_url  # local fallback path stored in blob_url field

    if not source_url:
        raise HTTPException(
            status_code=400,
            detail=f"No accessible video file. blob_url='{blob_url}', video_path='{video_path}'"
        )

    # 2. Download/copy video temporarily
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, f"{request.video_id}.mp4")
    media = None

    try:
        if source_url.startswith("http"):
            print(f"[YouTube] Downloading video from: {source_url}")
            resp = requests.get(source_url, stream=True, timeout=300)
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[YouTube] Downloaded {os.path.getsize(tmp_path) / 1024 / 1024:.1f} MB")
        else:
            # Local file
            import shutil
            print(f"[YouTube] Copying local file: {source_url}")
            shutil.copy2(source_url, tmp_path)

        # 3. Upload to YouTube
        from googleapiclient.http import MediaFileUpload

        print(f"[YouTube] Building YouTube service for user: {user_id}")
        youtube = _get_youtube_service(user_id)
        raw_title = video.get("title", "MiniTale Story")
        vid_category = video.get("category", "")
        vid_language = video.get("language", "")
        body = {
            "snippet": {
                "title": _build_viral_title(raw_title, vid_category, vid_language),
                "description": _build_viral_description(raw_title, vid_category, vid_language),
                "tags": _build_viral_tags(raw_title, vid_category, vid_language),
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        print(f"[YouTube] Starting upload...")
        media = MediaFileUpload(tmp_path, mimetype="video/mp4", resumable=True)
        insert_request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        # Resumable upload - execute in a loop to handle chunked transfers
        response = None
        while response is None:
            upload_status, response = insert_request.next_chunk()
            if upload_status:
                print(f"[YouTube] Upload progress: {int(upload_status.progress() * 100)}%")

        youtube_video_id = response["id"]
        youtube_url = f"https://youtube.com/watch?v={youtube_video_id}"
        print(f"[YouTube] Upload SUCCESS: {youtube_url}")

        # 4. Save upload metadata to the job document
        video["youtube_video_id"] = youtube_video_id
        video["youtube_url"] = youtube_url
        video["youtube_uploaded_at"] = datetime.utcnow().isoformat()
        cosmos_db.upsert_item("jobs", video)

        return YouTubeUploadResponse(youtube_video_id=youtube_video_id, youtube_url=youtube_url)

    except HTTPException:
        raise
    except Exception as e:
        print(f"[YouTube] Upload FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {str(e)[:200]}")
    finally:
        # Close MediaFileUpload file handle BEFORE deleting on Windows
        if media is not None:
            try:
                if hasattr(media, '_fd') and media._fd is not None:
                    media._fd.close()
                elif hasattr(media, 'stream') and media.stream is not None:
                    media.stream().close()
            except Exception:
                pass
            del media

        # Now safe to delete temp file
        import gc
        gc.collect()

        import time
        for attempt in range(3):
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(1)

        try:
            if os.path.exists(tmp_dir):
                os.rmdir(tmp_dir)
        except OSError:
            pass
