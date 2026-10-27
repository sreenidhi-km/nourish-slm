"""
config.py
=========
Backend application configuration settings.
Supports PostgreSQL with fallback to SQLite for zero-config local running.

Security notes:
- SECRET_KEY should be provided via the environment (see .env.example). If it is not,
  a random per-process key is generated, so tokens are valid only until the server
  restarts (fine for local dev, never rely on it in production).
- CORS origins are an explicit allow-list (CORS_ORIGINS, comma separated).
- The unauthenticated demo user is OFF unless ALLOW_DEMO_USER=true.
"""

import os
import secrets

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


class Settings:
    PROJECT_NAME: str = "Food SLM - AI Recipe Assistant"
    API_V1_STR: str = "/api"
    # No fixed fallback key: the repository is public, so a key written here could be used to forge tokens.
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(48)
    SECRET_KEY_FROM_ENV: bool = bool(os.environ.get("SECRET_KEY"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    ALLOW_DEMO_USER: bool = os.environ.get("ALLOW_DEMO_USER", "false").lower() == "true"
    CORS_ORIGINS: list = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # Optional regex for extra allowed origins, e.g. Vercel deployments
    CORS_ORIGIN_REGEX: str = os.environ.get("CORS_ORIGIN_REGEX", "") or None

    # Database URL: PostgreSQL or SQLite
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(PROJECT_ROOT, "food_slm.db")
    )
    PROCESSED_CSV_PATH: str = os.environ.get(
        "PROCESSED_CSV_PATH",
        os.path.join(PROJECT_ROOT, "data", "processed", "foodcom_cleaned.csv"),
    )
    # Diet planning data (built by scripts/build_diet_dataset.py)
    DIET_DB_PATH: str = os.environ.get(
        "DIET_DB_PATH", os.path.join(PROJECT_ROOT, "data", "processed", "diet_recipes.db")
    )
    USDA_FOODS_PATH: str = os.environ.get(
        "USDA_FOODS_PATH", os.path.join(PROJECT_ROOT, "data", "processed", "usda_foods.json")
    )


settings = Settings()
