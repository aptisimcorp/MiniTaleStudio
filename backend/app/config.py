import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Resolve .env path relative to THIS file (backend/app/config.py -> project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")
load_dotenv(_ENV_PATH)


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Azure Cosmos DB
    cosmos_db_connection_string: str = os.getenv("COSMOS_DB_CONNECTION_STRING", "")
    cosmos_db_database_name: str = os.getenv("COSMOS_DB_DATABASE_NAME", "minitale_studio")

    # Azure Blob Storage
    azure_storage_connection_string: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    azure_blob_container: str = "minitalestudio"

    # JWT Authentication
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "minitale-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # YouTube API
    youtube_client_id: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    youtube_client_secret: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    youtube_redirect_uri: str = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/oauth/callback")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Backend
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Paths
    assets_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")
    output_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")
    jobs_dir: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "jobs")

    # Video defaults
    default_fps: int = 24
    default_width: int = 1080
    default_height: int = 1920

    # Admin defaults
    admin_email: str = "minitalestudio75@gmail.com"
    admin_password: str = "Admin@1949"

    class Config:
        env_file = _ENV_PATH
        extra = "ignore"


settings = Settings()
