import os
import time
import traceback

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import settings

# Force chunked upload for files > 4 MB to avoid single-PUT timeouts.
# Each block is 8 MB and blocks upload in parallel.
_MAX_SINGLE_PUT_SIZE = 4 * 1024 * 1024    # 4 MB  -- anything larger uses blocks
_MAX_BLOCK_SIZE = 8 * 1024 * 1024          # 8 MB per block
_MAX_CONCURRENCY = 4                       # parallel block uploads


def _upload_timeout_for_size(file_size: int) -> int:
    """Return a generous upload timeout (seconds) based on file size.

    Assumes a worst-case sustained throughput of ~1 MB/s with headroom.
    Minimum 10 minutes, scales up for very large files.
    """
    base = 600                                    # 10 min minimum
    size_mb = file_size / (1024 * 1024)
    scaled = int(size_mb * 10)                    # ~10 s per MB
    return max(base, scaled)


def _max_retries_for_size(file_size: int) -> int:
    """More retries for larger files since partial progress is preserved."""
    size_mb = file_size / (1024 * 1024)
    if size_mb > 100:
        return 5
    if size_mb > 50:
        return 4
    return 3


def get_blob_service_client():
    """Create and return Azure Blob Storage service client."""
    conn_str = settings.azure_storage_connection_string
    if not conn_str:
        print("[BlobStorage] WARNING: AZURE_STORAGE_CONNECTION_STRING is empty.")
        return None
    # Quick sanity check: Blob Storage conn strings start with
    # "DefaultEndpointsProtocol=".  CosmosDB ones start with "AccountEndpoint=".
    if conn_str.startswith("AccountEndpoint="):
        print(
            "[BlobStorage] ERROR: AZURE_STORAGE_CONNECTION_STRING appears to be "
            "a CosmosDB connection string, not an Azure Blob Storage one. "
            "Expected format: DefaultEndpointsProtocol=https;AccountName=...;"
            "AccountKey=...;EndpointSuffix=core.windows.net"
        )
        return None
    try:
        client = BlobServiceClient.from_connection_string(
            conn_str,
            connection_timeout=120,
            read_timeout=600,
            max_single_put_size=_MAX_SINGLE_PUT_SIZE,
            max_block_size=_MAX_BLOCK_SIZE,
        )
        return client
    except Exception as e:
        print(f"[BlobStorage] ERROR creating BlobServiceClient: {e}")
        if "missing required connection details" in str(e).lower():
            print(
                "[BlobStorage] HINT: Make sure AZURE_STORAGE_CONNECTION_STRING "
                "is a Blob Storage connection string "
                "(DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;"
                "EndpointSuffix=core.windows.net), NOT a CosmosDB connection string."
            )
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


def upload_video_to_blob(local_path: str, blob_name: str | None = None, max_retries: int | None = None) -> str:
    """Upload a local video file to Azure Blob Storage and return the blob URL.

    Args:
        local_path: Path to the local video file.
        blob_name: Name to use in blob storage. Defaults to the local filename.
        max_retries: Number of retry attempts. Auto-scales with file size if None.

    Returns:
        The full blob URL on success, or the local path as fallback.
    """
    if not os.path.exists(local_path):
        print(f"[BlobStorage] ERROR: Local file not found: {local_path}")
        return local_path

    file_size = os.path.getsize(local_path)
    size_mb = file_size / (1024 * 1024)
    upload_timeout = _upload_timeout_for_size(file_size)
    retries = max_retries if max_retries is not None else _max_retries_for_size(file_size)
    num_blocks = (file_size // _MAX_BLOCK_SIZE) + 1

    print(f"[BlobStorage] Preparing upload: {local_path} "
          f"({size_mb:.1f} MB, ~{num_blocks} blocks of {_MAX_BLOCK_SIZE // (1024*1024)} MB, "
          f"concurrency={_MAX_CONCURRENCY}, timeout={upload_timeout}s, retries={retries})")

    client = get_blob_service_client()
    if client is None:
        print("[BlobStorage] No blob client available - returning local path as fallback.")
        return local_path

    if blob_name is None:
        blob_name = os.path.basename(local_path)

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            container_client = client.get_container_client(settings.azure_blob_container)

            # Ensure container exists
            if not container_client.exists():
                container_client.create_container()
                print(f"[BlobStorage] Container '{settings.azure_blob_container}' created on-the-fly.")

            blob_client = container_client.get_blob_client(blob_name)
            content_settings = ContentSettings(content_type="video/mp4")

            print(f"[BlobStorage] Uploading '{blob_name}' (attempt {attempt}/{retries})...")

            with open(local_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=content_settings,
                    max_concurrency=_MAX_CONCURRENCY,
                    timeout=upload_timeout,
                    connection_timeout=120,
                )

            blob_url = blob_client.url
            print(f"[BlobStorage] Upload SUCCESS: {blob_url}")
            return blob_url

        except Exception as e:
            last_error = e
            print(f"[BlobStorage] Attempt {attempt}/{retries} FAILED for '{blob_name}': {e}")
            if attempt < retries:
                wait = min(attempt * 10, 60)
                print(f"[BlobStorage] Retrying in {wait}s...")
                time.sleep(wait)

    # All retries exhausted
    print(f"[BlobStorage] Upload FAILED after {retries} attempts: {last_error}")
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


# Cache of already-uploaded character images: local_path -> blob_url
_character_image_cache: dict[str, str] = {}


def upload_character_image_to_blob(local_path: str) -> str:
    """Upload a character reference image to blob storage and return the public URL.

    Results are cached so the same image is only uploaded once per process lifetime.
    """
    if local_path in _character_image_cache:
        return _character_image_cache[local_path]

    if not os.path.exists(local_path):
        print(f"[BlobStorage] Character image not found: {local_path}")
        return ""

    client = get_blob_service_client()
    if client is None:
        print("[BlobStorage] No blob client - cannot upload character image")
        return ""

    # Build blob name like: characters/aanya/ghibli.jpg
    parts = local_path.replace("\\", "/").split("/")
    try:
        char_idx = parts.index("characters")
        blob_name = "/".join(parts[char_idx:])  # characters/aanya/ghibli.jpg
    except ValueError:
        blob_name = f"characters/{os.path.basename(local_path)}"

    try:
        container_client = client.get_container_client(settings.azure_blob_container)
        blob_client = container_client.get_blob_client(blob_name)

        ext = os.path.splitext(local_path)[1].lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        with open(local_path, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=mime),
                timeout=60,
            )

        blob_url = blob_client.url
        _character_image_cache[local_path] = blob_url
        print(f"[BlobStorage] Character image uploaded: {blob_name} -> {blob_url}")
        return blob_url

    except Exception as e:
        print(f"[BlobStorage] Character image upload failed: {e}")
        return ""


def get_character_image_blob_urls(local_paths: list[str]) -> list[str]:
    """Upload multiple character images to blob storage and return their public URLs."""
    urls = []
    for path in local_paths:
        url = upload_character_image_to_blob(path)
        if url:
            urls.append(url)
    return urls



