import os
import traceback
from datetime import datetime

from app.workers.celery_app import celery_app
from app.config import settings
from app.database import cosmos_db
from app.models import (
    ConfigurationCreate,
    JobStatus,
    PipelineContext,
    PipelineStep,
)
from app.services.story_generator import generate_story
from app.services.image_generator import generate_all_images
from app.services.narration_generator import generate_narration
from app.services.subtitle_generator import generate_subtitles
from app.services.video_assembler import assemble_video
from app.services.blob_storage import upload_video_to_blob, delete_local_file
from app.services.cleanup import cleanup_job_images
from app.services.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    delete_checkpoint,
    restore_story_from_checkpoint,
    step_already_done,
    can_resume_images,
)


def _update_job(job_id: str, updates: dict):
    """Update a job document. When the status (partition key) changes,
    the old document is deleted first to prevent duplicates."""
    items = cosmos_db.query_items(
        "jobs",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": job_id}],
    )
    if not items:
        return

    # Take the most recent entry if duplicates already exist
    item = max(items, key=lambda x: x.get("updated_at", ""))
    old_status = item.get("status")
    new_status = updates.get("status", old_status)

    item.update(updates)
    item["updated_at"] = datetime.utcnow().isoformat()

    # If status (partition key) changed, delete ALL old docs then create new one
    if new_status != old_status:
        for old_item in items:
            cosmos_db.delete_item("jobs", old_item["id"], old_item["status"])
        # Remove Cosmos system properties before re-creating
        for key in ["_rid", "_self", "_etag", "_attachments", "_ts"]:
            item.pop(key, None)
        cosmos_db.create_item("jobs", item)
    else:
        cosmos_db.upsert_item("jobs", item)


def _set_step(job_id: str, step: PipelineStep, extra: dict | None = None):
    """Update pipeline_step in the job document for live progress tracking."""
    updates = {"pipeline_step": step.value}
    if extra:
        updates.update(extra)
    _update_job(job_id, updates)


@celery_app.task(name="app.workers.tasks.run_video_pipeline", bind=True, max_retries=1)
def run_video_pipeline(self, job_id: str, config_dict: dict, user_id: str = "admin_user"):
    # Ensure DB connection in worker process
    if not cosmos_db.client:
        cosmos_db.connect()

    config = ConfigurationCreate(**config_dict)
    work_dir = os.path.join(settings.assets_dir, f"job_{job_id}")
    os.makedirs(work_dir, exist_ok=True)

    # Load any existing checkpoint (from a prior crashed run)
    checkpoint = load_checkpoint(work_dir)
    is_resume = checkpoint is not None
    if is_resume:
        print(f"[Pipeline:{job_id}] RESUMING from checkpoint: step={checkpoint.get('step')}")
    else:
        print(f"[Pipeline:{job_id}] Starting fresh run")

    _update_job(job_id, {
        "status": JobStatus.RUNNING.value,
        "user_id": user_id,
        "pipeline_step": PipelineStep.STORY.value,
    })

    ctx = PipelineContext(job_id=job_id, configuration=config, work_dir=work_dir)

    try:
        # ?? Step 1: Generate Story ???????????????????????????????????????
        if step_already_done(checkpoint, PipelineStep.STORY):
            print(f"[Pipeline:{job_id}] Story already generated - restoring from checkpoint")
            ctx.story = restore_story_from_checkpoint(checkpoint)
            if ctx.story is None:
                raise RuntimeError("Checkpoint says story done but data is missing")
        else:
            _set_step(job_id, PipelineStep.STORY)
            print(f"[Pipeline:{job_id}] Generating story...")
            ctx.story = generate_story(config)
            print(f"[Pipeline:{job_id}] Story: {ctx.story.title} "
                  f"({ctx.story.word_count} words, {len(ctx.story.scenes)} scenes)")

            _update_job(job_id, {
                "title": ctx.story.title,
                "script": ctx.story.full_text,
            })

            save_checkpoint(
                work_dir,
                PipelineStep.STORY,
                story_data=ctx.story.model_dump(),
            )

        # ?? Step 2: Generate Images ??????????????????????????????????????
        _set_step(job_id, PipelineStep.IMAGES)

        if step_already_done(checkpoint, PipelineStep.IMAGES):
            # Verify all images actually exist on disk
            missing = can_resume_images(work_dir, len(ctx.story.scenes))
            if not missing:
                print(f"[Pipeline:{job_id}] All {len(ctx.story.scenes)} images already exist - skipping")
                # Restore image paths
                images_dir = os.path.join(work_dir, "images")
                for scene in ctx.story.scenes:
                    scene.image_path = os.path.join(images_dir, f"scene_{scene.index:03d}.png")
            else:
                print(f"[Pipeline:{job_id}] {len(missing)} of {len(ctx.story.scenes)} images missing - regenerating only those")
                ctx.story.scenes = _generate_missing_images(
                    ctx.story.scenes, missing, config, work_dir
                )
        else:
            print(f"[Pipeline:{job_id}] Generating images...")
            # Check for partially completed images from a prior crash
            missing = can_resume_images(work_dir, len(ctx.story.scenes))
            if len(missing) < len(ctx.story.scenes):
                already = len(ctx.story.scenes) - len(missing)
                print(f"[Pipeline:{job_id}] Found {already} existing images, generating {len(missing)} remaining")
                ctx.story.scenes = _generate_missing_images(
                    ctx.story.scenes, missing, config, work_dir
                )
            else:
                ctx.story.scenes = generate_all_images(
                    ctx.story.scenes,
                    config.image_style,
                    work_dir,
                    character_descriptions=ctx.story.character_descriptions,
                )

        save_checkpoint(
            work_dir,
            PipelineStep.IMAGES,
            story_data=ctx.story.model_dump(),
        )

        # ?? Step 3: Generate Narration ???????????????????????????????????
        _set_step(job_id, PipelineStep.NARRATION)

        narration_file = os.path.join(work_dir, "audio", "narration.mp3")
        if step_already_done(checkpoint, PipelineStep.NARRATION) and os.path.exists(narration_file):
            print(f"[Pipeline:{job_id}] Narration already exists - skipping")
            ctx.narration_path = narration_file
        else:
            print(f"[Pipeline:{job_id}] Generating narration...")
            ctx.narration_path = generate_narration(
                ctx.story.full_text,
                config.language,
                config.voice_type,
                work_dir,
            )

        save_checkpoint(
            work_dir,
            PipelineStep.NARRATION,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
        )

        # ?? Step 4: Get audio duration + generate subtitles ??????????????
        _set_step(job_id, PipelineStep.SUBTITLES)

        from moviepy.editor import AudioFileClip
        audio = AudioFileClip(ctx.narration_path)
        total_duration = audio.duration
        audio.close()

        subtitle_file = os.path.join(work_dir, "subtitles", "story.srt")
        if step_already_done(checkpoint, PipelineStep.SUBTITLES) and os.path.exists(subtitle_file):
            print(f"[Pipeline:{job_id}] Subtitles already exist - skipping")
            ctx.subtitle_path = subtitle_file
        else:
            print(f"[Pipeline:{job_id}] Generating subtitles...")
            ctx.subtitle_path = generate_subtitles(ctx.story.scenes, total_duration, work_dir)

        save_checkpoint(
            work_dir,
            PipelineStep.SUBTITLES,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
            subtitle_path=ctx.subtitle_path,
        )

        # ?? Step 5: Assemble Video ???????????????????????????????????????
        _set_step(job_id, PipelineStep.ASSEMBLING)

        # Check if a video was already assembled in a prior run
        prior_video = checkpoint.get("video_path") if checkpoint else None
        if prior_video and os.path.exists(prior_video):
            print(f"[Pipeline:{job_id}] Video already assembled - skipping")
            ctx.video_path = prior_video
        else:
            print(f"[Pipeline:{job_id}] Assembling video...")
            ctx.video_path = assemble_video(
                ctx.story.scenes,
                ctx.narration_path,
                ctx.subtitle_path,
                config.subtitle_style,
                work_dir,
                watermark_path=config.watermark_path,
                splash_start_path=config.splash_start_path,
                splash_end_path=config.splash_end_path,
                background_music=config.background_music,
                category=config.category.value if hasattr(config.category, 'value') else str(config.category),
            )

        save_checkpoint(
            work_dir,
            PipelineStep.ASSEMBLING,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
            subtitle_path=ctx.subtitle_path,
            video_path=ctx.video_path,
        )

        # ?? Step 6: Upload to Azure Blob Storage ?????????????????????????
        _set_step(job_id, PipelineStep.UPLOADING)

        # Check if blob upload already succeeded in a prior run
        prior_blob = checkpoint.get("blob_url") if checkpoint else None
        if prior_blob and prior_blob.startswith("http"):
            print(f"[Pipeline:{job_id}] Blob already uploaded - skipping")
            blob_url = prior_blob
        else:
            print(f"[Pipeline:{job_id}] Uploading to Azure Blob Storage...")
            blob_url = upload_video_to_blob(ctx.video_path)

        save_checkpoint(
            work_dir,
            PipelineStep.UPLOADING,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
            subtitle_path=ctx.subtitle_path,
            video_path=ctx.video_path,
            blob_url=blob_url,
        )

        # ?? Step 7: Cleanup ??????????????????????????????????????????????
        _set_step(job_id, PipelineStep.CLEANUP)
        print(f"[Pipeline:{job_id}] Cleaning up temporary files...")

        # Delete local video only if blob upload returned a real URL
        if blob_url and blob_url.startswith("http"):
            delete_local_file(ctx.video_path)

            # Remove entire work directory (images, audio, subtitles, checkpoint)
            # since the final video is safely in blob storage now.
            import shutil
            if os.path.isdir(work_dir):
                try:
                    shutil.rmtree(work_dir)
                    print(f"[Pipeline:{job_id}] Removed work directory: {work_dir}")
                except OSError as e:
                    print(f"[Pipeline:{job_id}] Failed to remove work dir: {e}")
        else:
            # Blob upload failed - keep local files as fallback, only clean images
            cleanup_job_images(work_dir)
            delete_checkpoint(work_dir)

        # ?? Done ?????????????????????????????????????????????????????????
        _update_job(job_id, {
            "status": JobStatus.COMPLETED.value,
            "pipeline_step": PipelineStep.DONE.value,
            "video_path": ctx.video_path,
            "blob_url": blob_url,
            "title": ctx.story.title,
            "script": ctx.story.full_text,
            "user_id": user_id,
        })
        print(f"[Pipeline:{job_id}] COMPLETED - {blob_url or ctx.video_path}")
        return {
            "job_id": job_id,
            "status": "completed",
            "video_path": ctx.video_path,
            "blob_url": blob_url,
        }

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
        _update_job(job_id, {
            "status": JobStatus.FAILED.value,
            "pipeline_step": "failed",
            "error": error_msg[:2000],
            "user_id": user_id,
        })
        print(f"[Pipeline:{job_id}] FAILED: {error_msg}")
        # Don't re-raise - let the worker stay alive for the next job
        return {"job_id": job_id, "status": "failed", "error": str(exc)[:200]}


def _generate_missing_images(scenes, missing_indices, config, work_dir):
    """Generate only the missing scene images, preserving existing ones."""
    from app.services.image_generator import generate_scene_image

    images_dir = os.path.join(work_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    for scene in scenes:
        img_path = os.path.join(images_dir, f"scene_{scene.index:03d}.png")
        if scene.index in missing_indices:
            # Generate this image
            path = generate_scene_image(
                scene,
                config.image_style,
                images_dir,
                character_descriptions=config.custom_category or "",
            )
            scene.image_path = path
        else:
            # Already exists
            scene.image_path = img_path

    return scenes
