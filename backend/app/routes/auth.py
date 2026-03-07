from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.auth import verify_password, create_access_token, hash_password
from app.config import settings
from app.database import cosmos_db
from app.models import LoginRequest, LoginResponse

router = APIRouter()


def seed_admin_user():
    """Insert default admin user if not already present."""
    existing = cosmos_db.query_items(
        "users",
        "SELECT * FROM c WHERE c.email = @email",
        [{"name": "@email", "value": settings.admin_email}],
    )
    if existing:
        return

    admin_doc = {
        "id": "admin_user",
        "email": settings.admin_email,
        "password_hash": hash_password(settings.admin_password),
        "role": "admin",
        "created_at": datetime.utcnow().isoformat(),
    }
    cosmos_db.create_item("users", admin_doc)
    print(f"[Auth] Default admin user seeded: {settings.admin_email}")


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    users = cosmos_db.query_items(
        "users",
        "SELECT * FROM c WHERE c.email = @email",
        [{"name": "@email", "value": request.email}],
    )
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = users[0]
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user_id=user["id"], email=user["email"], role=user.get("role", "admin"))
    return LoginResponse(access_token=token)
