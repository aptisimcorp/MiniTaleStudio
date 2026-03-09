"""Grok (xAI) video generation service.

Generates silent animated video clips for each scene using the official xAI SDK.
Character reference images are provided as public Azure Blob URLs.
All clips are stripped of audio before returning, since the pipeline adds
narration, background music, and effects in the assembly step.
"""

import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import requests
from xai_sdk.sync.client import Client as XAIClient

from app.config import settings
from app.services.blob_storage import get_character_image_blob_urls

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grok configuration
# ---------------------------------------------------------------------------
GROK_VIDEO_MODEL = "grok-imagine-video"

# Default video settings for vertical shorts
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_CLIP_DURATION = 5  # seconds per scene clip

# Cost tracking
GROK_COST_PER_CLIP = 0.10

# Retry / timeout settings
MAX_RETRIES = 3
SDK_TIMEOUT = timedelta(minutes=10)     # max wait for SDK polling
SDK_POLL_INTERVAL = timedelta(seconds=5)  # poll frequency
DOWNLOAD_TIMEOUT = 180                  # seconds for video download

# Parallel generation
MAX_PARALLEL_SCENES = 3


def _get_xai_client() -> XAIClient:
    """Create an xAI SDK client using the configured API key."""
    api_key = settings.grok_api_key
    if not api_key:
        raise RuntimeError("GROK_API_KEY is not configured")
    return XAIClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_cinematic_prompt(
    scene_prompt: str,
    style: str,
    character_descriptions: str = "",
) -> str:
    """Build a structured cinematic prompt for Grok text-to-video generation.

    Injects full character descriptions into every scene prompt so the
    AI renders characters consistently across all clips.
    """
    parts = []

    # Character identity block -- repeated in EVERY scene prompt so the
    # text-to-video model sees the same character details each time.
    if character_descriptions:
        parts.append(
            "CHARACTERS IN THIS STORY (maintain exact appearance in every frame):\n"
            f"{character_descriptions}\n"
        )

    parts.append(f"SCENE DESCRIPTION:\n{scene_prompt}")

    parts.append(
        f"\nVisual Style: {style}\n"
        "Maintain consistent character appearance across the entire video.\n"
        "Cinematic animated scene.\n"
        "No audio. No dialogue. No background music.\n"
        "Visual animation only.\n"
        "Vertical 9:16 video.\n"
        "Smooth character motion."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Audio stripping (safety)
# ---------------------------------------------------------------------------
def _strip_audio(video_path: str) -> str:
    """Remove audio track from a video clip to guarantee silence.

    Tries FFmpeg first (fast, no re-encode), falls back to MoviePy.
    Returns the path to the silent clip (overwrites in place).
    """
    silent_path = video_path.replace(".mp4", "_silent.mp4")

    # Try FFmpeg (preferred -- fast copy, no re-encode)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-an", "-c:v", "copy", silent_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and os.path.exists(silent_path):
            os.replace(silent_path, video_path)
            logger.debug("Audio stripped via FFmpeg: %s", video_path)
            return video_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # FFmpeg not available or timed out

    # Fallback: MoviePy
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(video_path)
        clip = clip.without_audio()
        clip.write_videofile(silent_path, codec="libx264", logger=None)
        clip.close()
        os.replace(silent_path, video_path)
        logger.debug("Audio stripped via MoviePy: %s", video_path)
        return video_path
    except Exception as e:
        logger.warning("Audio strip failed for %s: %s (proceeding with original)", video_path, e)
        # Clean up partial file
        if os.path.exists(silent_path):
            os.remove(silent_path)
        return video_path


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------
def generate_scene_video(
    scene_prompt: str,
    scene_index: int,
    character_image_urls: list[str],
    style: str,
    work_dir: str,
    character_descriptions: str = "",
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    duration: int = DEFAULT_CLIP_DURATION,
) -> str:
    """Generate a silent video clip for a single scene via the xAI SDK.

    Uses pure text-to-video generation. Character consistency is achieved
    by injecting detailed character descriptions into every scene prompt
    rather than using a reference image.

    Args:
        scene_prompt: The video prompt describing the scene.
        scene_index: Scene number for file naming.
        character_image_urls: Not used (kept for API compatibility).
        style: Art style (realistic, 3dtoon, ghibli, lego).
        work_dir: Working directory for this job.
        character_descriptions: Full character appearance text to inject.
        aspect_ratio: Video aspect ratio (default 9:16 for shorts).
        duration: Duration in seconds per clip.

    Returns:
        Path to the generated silent MP4 clip.
    """
    logger.info("GROK_API_KEY configured: %s", bool(settings.grok_api_key))

    clips_dir = os.path.join(work_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    output_path = os.path.join(clips_dir, f"scene_{scene_index:03d}.mp4")

    # Build prompt with character descriptions embedded
    prompt = _build_cinematic_prompt(scene_prompt, style, character_descriptions)

    logger.info("Scene %d: Generating via xAI SDK text-to-video (model=%s)", scene_index, GROK_VIDEO_MODEL)

    # -- Generate with retry ------------------------------------------------
    video_response = None
    for retry in range(MAX_RETRIES):
        client = None
        try:
            client = _get_xai_client()
            # SDK .generate() submits the request and polls until completion
            video_response = client.video.generate(
                prompt=prompt,
                model=GROK_VIDEO_MODEL,
                duration=duration,
                aspect_ratio=aspect_ratio,
                timeout=SDK_TIMEOUT,
                interval=SDK_POLL_INTERVAL,
            )
            break
        except Exception as e:
            if retry == MAX_RETRIES - 1:
                logger.error(
                    "Scene %d: xAI SDK failed after %d retries: %s",
                    scene_index, MAX_RETRIES, e,
                )
                raise
            logger.warning(
                "Scene %d: xAI SDK attempt %d failed: %s - retrying...",
                scene_index, retry + 1, e,
            )
            time.sleep(5 * (retry + 1))
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    video_url = video_response.url
    if not video_url:
        raise RuntimeError(f"xAI SDK did not return a video URL for scene {scene_index}")

    logger.info("Scene %d: Video ready at %s", scene_index, video_url)

    # -- Download clip ------------------------------------------------------
    logger.info("Scene %d: Downloading clip...", scene_index)
    for retry in range(MAX_RETRIES):
        try:
            video_resp = requests.get(video_url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            video_resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in video_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            break
        except Exception as e:
            if retry == MAX_RETRIES - 1:
                raise
            logger.warning("Scene %d: Download attempt %d failed: %s", scene_index, retry + 1, e)
            time.sleep(3)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    logger.info("Scene %d: Downloaded %.1f MB -> %s", scene_index, size_mb, output_path)

    # -- Strip audio (safety) -----------------------------------------------
    _strip_audio(output_path)

    return output_path


# ---------------------------------------------------------------------------
# Batch generation (parallel)
# ---------------------------------------------------------------------------
def generate_all_scene_videos(
    scenes: list,
    character_image_urls: list[str],
    style: str,
    work_dir: str,
    character_descriptions: str = "",
    max_parallel: int = MAX_PARALLEL_SCENES,
) -> list:
    """Generate video clips for all scenes, optionally in parallel.

    Args:
        scenes: List of Scene objects with video_prompt / image_prompt.
        character_image_urls: Kept for API compat (not used in text-to-video).
        style: Art style name.
        work_dir: Job working directory.
        character_descriptions: Character appearance block injected into every prompt.
        max_parallel: Maximum concurrent scene generations.

    Returns:
        Updated list of scenes with video_clip_path set.
    """
    def _gen(scene):
        prompt = scene.video_prompt or scene.image_prompt
        clip_path = generate_scene_video(
            scene_prompt=prompt,
            scene_index=scene.index,
            character_image_urls=character_image_urls,
            style=style,
            work_dir=work_dir,
            character_descriptions=character_descriptions,
        )
        return scene.index, clip_path

    scene_map = {s.index: s for s in scenes}

    if max_parallel > 1 and len(scenes) > 1:
        logger.info("Generating %d scenes in parallel (max_workers=%d)", len(scenes), max_parallel)
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {executor.submit(_gen, s): s.index for s in scenes}
            for future in as_completed(futures):
                idx, clip_path = future.result()
                scene_map[idx].video_clip_path = clip_path
    else:
        for scene in scenes:
            _, clip_path = _gen(scene)
            scene.video_clip_path = clip_path

    return scenes
