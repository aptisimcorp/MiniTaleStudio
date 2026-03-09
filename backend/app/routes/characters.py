"""Character management routes.

GET  /characters          -- list all characters (any authenticated user)
POST /characters          -- create a new character (admin)
PUT  /characters/{id}     -- update a character (admin)
DELETE /characters/{id}   -- delete a character (admin)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.auth import get_current_user
from app.database import cosmos_db
from app.services.character_service import get_all_characters

router = APIRouter(prefix="/api/characters", tags=["Characters"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CharacterCreate(BaseModel):
    name: str
    displayName: str
    role: str = ""
    descriptionPrompt: str = ""
    images: dict = {}


class CharacterUpdate(BaseModel):
    displayName: str | None = None
    role: str | None = None
    descriptionPrompt: str | None = None
    images: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def list_characters(user: dict = Depends(get_current_user)):
    """Return all characters from CosmosDB."""
    characters = get_all_characters()
    return {"characters": characters}


@router.post("")
async def create_character(body: CharacterCreate, user: dict = Depends(get_current_user)):
    """Create a new character."""
    char_id = body.name.lower().strip()
    existing = cosmos_db.query_items(
        "characters",
        "SELECT c.id FROM c WHERE c.id = @id",
        [{"name": "@id", "value": char_id}],
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Character '{char_id}' already exists")

    doc = {
        "id": char_id,
        "name": body.name.lower().strip(),
        "displayName": body.displayName,
        "role": body.role,
        "descriptionPrompt": body.descriptionPrompt,
        "images": body.images,
    }
    cosmos_db.create_item("characters", doc)
    return doc


@router.put("/{character_id}")
async def update_character(character_id: str, body: CharacterUpdate, user: dict = Depends(get_current_user)):
    """Update an existing character."""
    items = cosmos_db.query_items(
        "characters",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": character_id}],
    )
    if not items:
        raise HTTPException(status_code=404, detail="Character not found")

    doc = items[0]
    if body.displayName is not None:
        doc["displayName"] = body.displayName
    if body.role is not None:
        doc["role"] = body.role
    if body.descriptionPrompt is not None:
        doc["descriptionPrompt"] = body.descriptionPrompt
    if body.images is not None:
        doc["images"] = body.images

    cosmos_db.upsert_item("characters", doc)
    return doc


@router.delete("/{character_id}")
async def delete_character(character_id: str, user: dict = Depends(get_current_user)):
    """Delete a character."""
    items = cosmos_db.query_items(
        "characters",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": character_id}],
    )
    if not items:
        raise HTTPException(status_code=404, detail="Character not found")

    doc = items[0]
    cosmos_db.delete_item("characters", character_id, doc["role"])
    return {"message": f"Character '{character_id}' deleted"}
