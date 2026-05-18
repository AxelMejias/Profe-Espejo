from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:280502@localhost:5432/foodstore_db"
    SECRET_KEY: str = "change-this-super-secret-key-min-32-chars-very-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    GOOGLE_CLIENT_ID: str = "294873652507-1bcbqukkqdokhsdv0u76i2pdhhnb19vm.apps.googleusercontent.com"
    N8N_WEBHOOK_URL: str = "https://akcel11.app.n8n.cloud/webhook/food-store-reset"
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
