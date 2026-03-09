"""Character service -- reads character data from CosmosDB.

On first startup the seed function imports characters.json into the
'characters' container so existing data is preserved.  After that the
JSON file is no longer used at runtime.
"""

import json
import logging
import os
from typing import Optional

from app.config import settings
from app.database import cosmos_db

logger = logging.getLogger(__name__)

# Project root (MiniTaleStudio/) -- backend/app/services/ -> 3 levels up = backend/, 4 = repo root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Path to the legacy JSON file (used only for one-time seed)
_CHARACTERS_JSON = os.path.join(_PROJECT_ROOT, "assets", "images", "characters", "characters.json")

# New canonical location for character images
_CHARACTERS_IMG_DIR = os.path.join(_PROJECT_ROOT, "frontend", "public", "characters")


# ---------------------------------------------------------------------------
# Seed (one-time migration)
# ---------------------------------------------------------------------------
def _remap_image_paths(images: dict) -> dict:
    """Convert legacy asset paths to the new frontend/public location.

    Old: assets/images/characters/aanya/ghibli.jpg
    New: frontend/public/characters/aanya/ghibli.jpg
    """
    remapped = {}
    for style, old_path in images.items():
        new_path = old_path.replace(
            "assets/images/characters/", "frontend/public/characters/"
        )
        remapped[style] = new_path
    return remapped


def seed_characters_from_json():
    """Import characters from the legacy characters.json into CosmosDB.

    Runs at startup.  Skips characters that already exist so re-running
    is safe (idempotent).
    """
    if not os.path.exists(_CHARACTERS_JSON):
        logger.info("No characters.json found at %s -- skipping seed", _CHARACTERS_JSON)
        return

    with open(_CHARACTERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    characters = data.get("characters", [])
    if not characters:
        return

    existing = cosmos_db.query_items("characters", "SELECT c.id FROM c", [])
    existing_ids = {item["id"] for item in existing}

    seeded = 0
    for char in characters:
        char_id = char["name"].lower()
        if char_id in existing_ids:
            continue

        doc = {
            "id": char_id,
            "name": char["name"],
            "displayName": char.get("displayName", char["name"]),
            "role": char.get("role", ""),
            "descriptionPrompt": char.get("descriptionPrompt", ""),
            "images": _remap_image_paths(char.get("images", {})),
        }
        cosmos_db.create_item("characters", doc)
        seeded += 1

    logger.info("Character seed: %d new, %d already existed", seeded, len(existing_ids))


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
def get_all_characters() -> list[dict]:
    """Return every character from CosmosDB."""
    return cosmos_db.query_items(
        "characters",
        "SELECT * FROM c ORDER BY c.displayName",
        [],
    )


def get_characters_by_names(names: list[str]) -> list[dict]:
    """Return character docs whose name matches any in *names*."""
    if not names:
        return []
    name_set = {n.lower() for n in names}
    all_chars = get_all_characters()
    return [c for c in all_chars if c["name"].lower() in name_set]


def get_character_image_path(character_name: str, style: str) -> Optional[str]:
    """Return the absolute path to a character image for a given style.

    Images live under frontend/public/characters/<name>/<style>.jpg.
    Falls back to direct path resolution from the CosmosDB doc.
    """
    chars = get_characters_by_names([character_name])
    if not chars:
        return None

    char = chars[0]

    # Try direct filesystem lookup first (canonical location)
    direct = os.path.join(_CHARACTERS_IMG_DIR, character_name.lower(), f"{style}.jpg")
    if os.path.exists(direct):
        return direct

    # Fall back to the relative path stored in CosmosDB
    relative = char.get("images", {}).get(style)
    if not relative:
        return None

    abs_path = os.path.join(_PROJECT_ROOT, relative)
    return abs_path if os.path.exists(abs_path) else None


def build_character_prompt_block(character_names: list[str]) -> str:
    """Build a prompt block describing selected characters for story generation."""
    chars = get_characters_by_names(character_names)
    if not chars:
        return ""

    lines = []
    for c in chars:
        display = c.get("displayName", c["name"])
        desc = c.get("descriptionPrompt", "")
        role = c.get("role", "")
        lines.append(f"- {display} ({role}): {desc}")

    return (
        "CHARACTERS (use ONLY these characters in the story):\n"
        + "\n".join(lines)
        + "\n\n"
        "RULES:\n"
        "- Use ONLY the characters listed above\n"
        "- Maintain their exact visual descriptions across ALL scenes\n"
        "- Characters must appear consistently throughout the story\n"
    )


def get_character_reference_images(character_names: list[str], style: str) -> list[str]:
    """Return list of absolute image paths for the selected characters."""
    paths = []
    for name in character_names:
        path = get_character_image_path(name, style)
        if path:
            paths.append(path)
    return paths
