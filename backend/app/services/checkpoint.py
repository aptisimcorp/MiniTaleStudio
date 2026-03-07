"""Checkpoint system for the video generation pipeline.

Saves pipeline progress to a JSON file in the job's work directory.
On resume (after crash/restart), loads the checkpoint and skips
already-completed steps to avoid wasting OpenAI credits and time.

Checkpoint file: <work_dir>/checkpoint.json
"""

import json
import os
from typing import Optional

from app.models import PipelineStep, Scene, StoryResult


CHECKPOINT_FILENAME = "checkpoint.json"


def _checkpoint_path(work_dir: str) -> str:
    return os.path.join(work_dir, CHECKPOINT_FILENAME)


def save_checkpoint(
    work_dir: str,
    step: PipelineStep,
    story_data: Optional[dict] = None,
    narration_path: Optional[str] = None,
    subtitle_path: Optional[str] = None,
    video_path: Optional[str] = None,
    blob_url: Optional[str] = None,
):
    """Save current pipeline progress to disk."""
    data = {
        "step": step.value,
        "story_data": story_data,
        "narration_path": narration_path,
        "subtitle_path": subtitle_path,
        "video_path": video_path,
        "blob_url": blob_url,
    }
    path = _checkpoint_path(work_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_checkpoint(work_dir: str) -> Optional[dict]:
    """Load checkpoint from disk. Returns None if no checkpoint exists."""
    path = _checkpoint_path(work_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[Checkpoint] Failed to load {path}: {e}")
        return None


def delete_checkpoint(work_dir: str):
    """Remove checkpoint file after successful completion."""
    path = _checkpoint_path(work_dir)
    if os.path.exists(path):
        os.remove(path)


def restore_story_from_checkpoint(checkpoint: dict) -> Optional[StoryResult]:
    """Reconstruct a StoryResult from checkpoint data."""
    story_data = checkpoint.get("story_data")
    if not story_data:
        return None
    try:
        return StoryResult(**story_data)
    except Exception as e:
        print(f"[Checkpoint] Failed to restore story: {e}")
        return None


def step_already_done(checkpoint: Optional[dict], target_step: PipelineStep) -> bool:
    """Check if a given step was already completed in a prior run.

    The checkpoint stores the LAST COMPLETED step. If that step is at or past
    the target step in the pipeline order, the target step was already done.
    """
    if checkpoint is None:
        return False

    from app.models import PIPELINE_STEP_ORDER

    saved_step_value = checkpoint.get("step")
    if not saved_step_value:
        return False

    try:
        saved_step = PipelineStep(saved_step_value)
    except ValueError:
        return False

    saved_idx = PIPELINE_STEP_ORDER.index(saved_step) if saved_step in PIPELINE_STEP_ORDER else -1
    target_idx = PIPELINE_STEP_ORDER.index(target_step) if target_step in PIPELINE_STEP_ORDER else 999

    return saved_idx >= target_idx


def can_resume_images(work_dir: str, total_scenes: int) -> list[int]:
    """Check which scene images already exist on disk.

    Returns a list of scene indices that are MISSING and need to be generated.
    """
    images_dir = os.path.join(work_dir, "images")
    if not os.path.isdir(images_dir):
        return list(range(total_scenes))

    missing = []
    for i in range(total_scenes):
        img_path = os.path.join(images_dir, f"scene_{i:03d}.png")
        if not os.path.exists(img_path):
            missing.append(i)

    return missing
