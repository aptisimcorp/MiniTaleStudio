import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from app.auth import get_current_user
from app.database import cosmos_db
from app.models import ConfigurationCreate, ConfigurationResponse

router = APIRouter()


@router.post("/configurations", response_model=ConfigurationResponse)
async def create_configuration(config: ConfigurationCreate, user: dict = Depends(get_current_user)):
    item = config.model_dump()
    item["id"] = str(uuid.uuid4())
    item["user_id"] = user["user_id"]
    item["created_at"] = datetime.utcnow().isoformat()
    saved = cosmos_db.create_item("configurations", item)
    return ConfigurationResponse(**saved)


@router.get("/configurations")
async def list_configurations(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    items = cosmos_db.query_items(
        "configurations",
        "SELECT * FROM c WHERE c.user_id = @uid ORDER BY c._ts DESC",
        [{"name": "@uid", "value": user_id}],
    )
    return items


@router.get("/configurations/{config_id}")
async def get_configuration(config_id: str, user: dict = Depends(get_current_user)):
    items = cosmos_db.query_items(
        "configurations",
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": config_id}],
    )
    if not items:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return items[0]
