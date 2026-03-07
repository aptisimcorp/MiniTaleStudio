import os
import shutil
import time

from app.config import settings

# Folders older than this many minutes will be cleaned up
CLEANUP_AGE_MINUTES = 30


def cleanup_old_job_folders():
    """Scan the jobs/assets directory and delete folders older than CLEANUP_AGE_MINUTES."""
    dirs_to_scan = [settings.assets_dir, settings.jobs_dir]

    now = time.time()
    cutoff = now - (CLEANUP_AGE_MINUTES * 60)

    for base_dir in dirs_to_scan:
        if not os.path.isdir(base_dir):
            continue

        for entry in os.listdir(base_dir):
            folder_path = os.path.join(base_dir, entry)

            # Only process job folders (prefixed with "job_")
            if not os.path.isdir(folder_path) or not entry.startswith("job_"):
                continue

            # Check folder modification time
            mtime = os.path.getmtime(folder_path)
            if mtime < cutoff:
                try:
                    shutil.rmtree(folder_path)
                    print(f"[Cleanup] Removed old job folder: {folder_path}")
                except OSError as e:
                    print(f"[Cleanup] Error removing {folder_path}: {e}")


def cleanup_job_images(work_dir: str):
    """Delete all generated images in a job work directory after video assembly."""
    if not os.path.isdir(work_dir):
        return

    # Clean the images subdirectory (where generate_all_images writes)
    images_dir = os.path.join(work_dir, "images")
    if os.path.isdir(images_dir):
        try:
            shutil.rmtree(images_dir)
            print(f"[Cleanup] Deleted images directory: {images_dir}")
        except OSError as e:
            print(f"[Cleanup] Error deleting images dir: {e}")

    # Also clean any top-level image files
    for entry in os.listdir(work_dir):
        file_path = os.path.join(work_dir, entry)
        if os.path.isfile(file_path) and entry.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            try:
                os.remove(file_path)
                print(f"[Cleanup] Deleted temp image: {file_path}")
            except OSError:
                pass
