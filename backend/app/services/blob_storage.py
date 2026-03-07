import os
import time
import traceback

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import settings

# Upload timeout: 10 minutes for large video files
_UPLOAD_TIMEOUT = 600


def get_blob_service_client():
    """Create and return Azure Blob Storage service client."""
    conn_str = settings.azure_storage_connection_string
    if not conn_str:
        print("[BlobStorage] WARNING: AZURE_STORAGE_CONNECTION_STRING is empty.")
        return None
    try:
        client = BlobServiceClient.from_connection_string(
            conn_str,
            connection_timeout=30,
            read_timeout=_UPLOAD_TIMEOUT,
        )
        return client
    except Exception as e:
        print(f"[BlobStorage] ERROR creating BlobServiceClient: {e}")
        return None


def ensure_container_exists():
    """Create the blob container if it does not exist."""
    client = get_blob_service_client()
    if client is None:
        return
    try:
        container_client = client.get_container_client(settings.azure_blob_container)
        if not container_client.exists():
            client.create_container(settings.azure_blob_container)
            print(f"[BlobStorage] Container '{settings.azure_blob_container}' created.")
        else:
            print(f"[BlobStorage] Container '{settings.azure_blob_container}' already exists.")
    except Exception as e:
        print(f"[BlobStorage] Container check/create error: {e}")


def upload_video_to_blob(local_path: str, blob_name: str | None = None, max_retries: int = 3) -> str:
    """Upload a local video file to Azure Blob Storage and return the blob URL.

    Args:
        local_path: Path to the local video file.
        blob_name: Name to use in blob storage. Defaults to the local filename.
        max_retries: Number of retry attempts on transient failures.

    Returns:
        The full blob URL on success, or the local path as fallback.
    """
    if not os.path.exists(local_path):
        print(f"[BlobStorage] ERROR: Local file not found: {local_path}")
        return local_path

    file_size = os.path.getsize(local_path)
    print(f"[BlobStorage] Preparing upload: {local_path} ({file_size / 1024 / 1024:.1f} MB)")

    client = get_blob_service_client()
    if client is None:
        print("[BlobStorage] No blob client available - returning local path as fallback.")
        return local_path

    if blob_name is None:
        blob_name = os.path.basename(local_path)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            container_client = client.get_container_client(settings.azure_blob_container)

            # Ensure container exists
            if not container_client.exists():
                container_client.create_container()
                print(f"[BlobStorage] Container '{settings.azure_blob_container}' created on-the-fly.")

            blob_client = container_client.get_blob_client(blob_name)
            content_settings = ContentSettings(content_type="video/mp4")

            # Force staged (block) upload for files larger than 4 MB to avoid
            # single-PUT timeouts on high-latency connections.
            blob_client.max_single_put_size = 4 * 1024 * 1024
            blob_client.max_block_size = 4 * 1024 * 1024

            print(f"[BlobStorage] Uploading '{blob_name}' (attempt {attempt}/{max_retries})...")

            with open(local_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=content_settings,
                    max_concurrency=1,
                    timeout=_UPLOAD_TIMEOUT,
                    connection_timeout=60,
                )

            blob_url = blob_client.url
            print(f"[BlobStorage] Upload SUCCESS: {blob_url}")
            return blob_url

        except Exception as e:
            last_error = e
            print(f"[BlobStorage] Attempt {attempt}/{max_retries} FAILED for '{blob_name}': {e}")
            if attempt < max_retries:
                wait = attempt * 5  # 5s, 10s backoff
                print(f"[BlobStorage] Retrying in {wait}s...")
                time.sleep(wait)

    # All retries exhausted
    print(f"[BlobStorage] Upload FAILED after {max_retries} attempts: {last_error}")
    print(f"[BlobStorage] Traceback: {traceback.format_exc()}")
    return local_path


def delete_local_file(path: str):
    """Delete a local file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"[Cleanup] Deleted local file: {path}")
    except OSError as e:
        print(f"[Cleanup] Error deleting {path}: {e}")

