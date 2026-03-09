import os
import traceback
from datetime import datetime

from app.workers.celery_app import celery_app
from app.config import settings
from app.database import cosmos_db
from app.models import (
    AIService,
    ConfigurationCreate,
    JobStatus,
    PipelineContext,
    PipelineStep,
)
from app.services.story_generator import generate_story
from app.services.image_generator import generate_all_images
from app.services.narration_generator import generate_narration
from app.services.subtitle_generator import generate_subtitles
from app.services.video_assembler import assemble_video, assemble_video_from_clips
from app.services.blob_storage import upload_video_to_blob, delete_local_file, get_character_image_blob_urls
from app.services.cleanup import cleanup_job_images
from app.services.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    delete_checkpoint,
    restore_story_from_checkpoint,
    step_already_done,
    can_resume_images,
)
from app.services.character_service import build_character_prompt_block, get_character_reference_images
from app.services.cost_tracker import VideoCostTracker


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
    cost = VideoCostTracker()
    is_grok = config.ai_service == AIService.GROK

    try:
        # -- Build character context (if characters selected) ---------------
        character_prompt_block = ""
        character_ref_images = []       # local paths (for OpenAI image prompts)
        character_ref_blob_urls = []    # public blob URLs (for Grok video API)
        if config.characters:
            character_prompt_block = build_character_prompt_block(config.characters)
            style_key = config.character_style.value if hasattr(config.character_style, 'value') else str(config.character_style)
            character_ref_images = get_character_reference_images(config.characters, style_key)
            # Upload character images to blob so Grok can access them via URL
            if is_grok and character_ref_images:
                character_ref_blob_urls = get_character_image_blob_urls(character_ref_images)
                print(f"[Pipeline:{job_id}] Character blob URLs: {len(character_ref_blob_urls)}")
            print(f"[Pipeline:{job_id}] Characters: {config.characters}, style={style_key}, "
                  f"ref images={len(character_ref_images)}")

        # == Step 1: Generate Story =========================================
        if step_already_done(checkpoint, PipelineStep.STORY):
            print(f"[Pipeline:{job_id}] Story already generated - restoring from checkpoint")
            ctx.story = restore_story_from_checkpoint(checkpoint)
            if ctx.story is None:
                raise RuntimeError("Checkpoint says story done but data is missing")
        else:
            _set_step(job_id, PipelineStep.STORY)
            print(f"[Pipeline:{job_id}] Generating story (ai_service={config.ai_service.value})...")
            ctx.story = generate_story(config, character_prompt_block=character_prompt_block)
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

        # == Step 2: Generate Images (OpenAI) OR Video Clips (Grok) =========
        if is_grok:
            # --- Grok path: generate silent video clips per scene ----------
            _set_step(job_id, PipelineStep.VIDEO_CLIPS)

            if step_already_done(checkpoint, PipelineStep.VIDEO_CLIPS):
                # Restore clip paths from checkpoint
                clips_dir = os.path.join(work_dir, "clips")
                all_exist = True
                for scene in ctx.story.scenes:
                    clip_path = os.path.join(clips_dir, f"scene_{scene.index:03d}.mp4")
                    if os.path.exists(clip_path):
                        scene.video_clip_path = clip_path
                    else:
                        all_exist = False

                if all_exist:
                    print(f"[Pipeline:{job_id}] All {len(ctx.story.scenes)} video clips exist - skipping")
                else:
                    print(f"[Pipeline:{job_id}] Some clips missing - regenerating...")
                    from app.services.grok_video_generator import generate_scene_video
                    style_key = config.character_style.value if hasattr(config.character_style, 'value') else str(config.character_style)
                    for scene in ctx.story.scenes:
                        if not scene.video_clip_path or not os.path.exists(scene.video_clip_path):
                            prompt = scene.video_prompt or scene.image_prompt
                            scene.video_clip_path = generate_scene_video(
                                scene_prompt=prompt,
                                scene_index=scene.index,
                                character_image_urls=character_ref_blob_urls,
                                style=style_key,
                                work_dir=work_dir,
                                character_descriptions=ctx.story.character_descriptions,
                            )
                            cost.add_grok_video_cost(1)
            else:
                print(f"[Pipeline:{job_id}] Generating Grok video clips...")
                from app.services.grok_video_generator import generate_all_scene_videos
                style_key = config.character_style.value if hasattr(config.character_style, 'value') else str(config.character_style)
                ctx.story.scenes = generate_all_scene_videos(
                    ctx.story.scenes,
                    character_ref_blob_urls,
                    style_key,
                    work_dir,
                    character_descriptions=ctx.story.character_descriptions,
                )
                cost.add_grok_video_cost(len(ctx.story.scenes))


            save_checkpoint(
                work_dir,
                PipelineStep.VIDEO_CLIPS,
                story_data=ctx.story.model_dump(),
            )
        else:
            # --- OpenAI path: generate images per scene --------------------
            _set_step(job_id, PipelineStep.IMAGES)

            if step_already_done(checkpoint, PipelineStep.IMAGES):
                missing = can_resume_images(work_dir, len(ctx.story.scenes))
                if not missing:
                    print(f"[Pipeline:{job_id}] All {len(ctx.story.scenes)} images already exist - skipping")
                    images_dir = os.path.join(work_dir, "images")
                    for scene in ctx.story.scenes:
                        scene.image_path = os.path.join(images_dir, f"scene_{scene.index:03d}.png")
                else:
                    print(f"[Pipeline:{job_id}] {len(missing)} images missing - regenerating")
                    ctx.story.scenes = _generate_missing_images(
                        ctx.story.scenes, missing, config, work_dir
                    )
                    cost.add_openai_image_cost(len(missing))
            else:
                print(f"[Pipeline:{job_id}] Generating images...")
                missing = can_resume_images(work_dir, len(ctx.story.scenes))
                if len(missing) < len(ctx.story.scenes):
                    already = len(ctx.story.scenes) - len(missing)
                    print(f"[Pipeline:{job_id}] Found {already} existing images, generating {len(missing)} remaining")
                    ctx.story.scenes = _generate_missing_images(
                        ctx.story.scenes, missing, config, work_dir
                    )
                    cost.add_openai_image_cost(len(missing))
                else:
                    ctx.story.scenes = generate_all_images(
                        ctx.story.scenes,
                        config.image_style,
                        work_dir,
                        character_descriptions=ctx.story.character_descriptions,
                    )
                    cost.add_openai_image_cost(len(ctx.story.scenes))

            save_checkpoint(
                work_dir,
                PipelineStep.IMAGES,
                story_data=ctx.story.model_dump(),
            )

        # == Step 3: Generate Narration =====================================
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
            cost.add_tts_cost(len(ctx.story.full_text))

        save_checkpoint(
            work_dir,
            PipelineStep.NARRATION,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
        )

        # == Step 4: Generate subtitles =====================================
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

        # == Step 5: Assemble Video =========================================
        _set_step(job_id, PipelineStep.ASSEMBLING)

        prior_video = checkpoint.get("video_path") if checkpoint else None
        if prior_video and os.path.exists(prior_video):
            print(f"[Pipeline:{job_id}] Video already assembled - skipping")
            ctx.video_path = prior_video
        else:
            category_val = config.category.value if hasattr(config.category, 'value') else str(config.category)
            assemble_kwargs = dict(
                scenes=ctx.story.scenes,
                narration_path=ctx.narration_path,
                subtitle_path=ctx.subtitle_path,
                subtitle_style=config.subtitle_style,
                work_dir=work_dir,
                watermark_path=config.watermark_path,
                splash_start_path=config.splash_start_path,
                splash_end_path=config.splash_end_path,
                background_music=config.background_music,
                category=category_val,
            )

            if is_grok:
                print(f"[Pipeline:{job_id}] Assembling video from Grok clips...")
                ctx.video_path = assemble_video_from_clips(**assemble_kwargs)
            else:
                print(f"[Pipeline:{job_id}] Assembling video from images...")
                ctx.video_path = assemble_video(**assemble_kwargs)

        save_checkpoint(
            work_dir,
            PipelineStep.ASSEMBLING,
            story_data=ctx.story.model_dump(),
            narration_path=ctx.narration_path,
            subtitle_path=ctx.subtitle_path,
            video_path=ctx.video_path,
        )

        # == Step 6: Upload to Azure Blob Storage ===========================
        _set_step(job_id, PipelineStep.UPLOADING)

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

        # == Step 7: Cleanup ================================================
        _set_step(job_id, PipelineStep.CLEANUP)
        print(f"[Pipeline:{job_id}] Cleaning up temporary files...")

        if blob_url and blob_url.startswith("http"):
            delete_local_file(ctx.video_path)
            import shutil
            if os.path.isdir(work_dir):
                try:
                    shutil.rmtree(work_dir)
                    print(f"[Pipeline:{job_id}] Removed work directory: {work_dir}")
                except OSError as e:
                    print(f"[Pipeline:{job_id}] Failed to remove work dir: {e}")
        else:
            cleanup_job_images(work_dir)
            delete_checkpoint(work_dir)

        # == Done ===========================================================
        ctx.total_cost = cost.total_cost
        _update_job(job_id, {
            "status": JobStatus.COMPLETED.value,
            "pipeline_step": PipelineStep.DONE.value,
            "video_path": ctx.video_path,
            "blob_url": blob_url,
            "title": ctx.story.title,
            "script": ctx.story.full_text,
            "user_id": user_id,
            "ai_service": config.ai_service.value,
            "character_style": config.character_style.value if hasattr(config.character_style, 'value') else "",
            "characters": config.characters,
            "cost": cost.to_dict(),
            "total_cost": cost.total_cost,
        })
        print(f"[Pipeline:{job_id}] COMPLETED - {blob_url or ctx.video_path} "
              f"(cost=${cost.total_cost:.4f})")
        return {
            "job_id": job_id,
            "status": "completed",
            "video_path": ctx.video_path,
            "blob_url": blob_url,
            "total_cost": cost.total_cost,
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
