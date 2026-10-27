"""
main.py
=======
FastAPI Application Entry Point for Food SLM.
Initializes database tables, configures CORS, mounts routers, and defines system health checks.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import Base, engine, ensure_columns
from backend.app.api import auth, users, chat, recipes, diet

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)
ensure_columns()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Industry-ready Small Language Model (SLM) Food Recipe Assistant API",
    version="1.0.0"
)

if not settings.SECRET_KEY_FROM_ENV:
    print("WARNING: SECRET_KEY not set; using a random per-process key. Set SECRET_KEY in .env.")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(recipes.router, prefix=settings.API_V1_STR)
app.include_router(diet.router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0"
    }

def _get_model_status_data():
    from model.inference import slm_engine
    adapter_exists = slm_engine.is_adapter_loaded
    label = slm_engine.model_label if adapter_exists else "Qwen3-4B · Base"
    mode = slm_engine.model_mode if adapter_exists else "base"
    return {
        "base_model": slm_engine.base_model_name,
        "adapter_dir": slm_engine.adapter_dir,
        "adapter_exists": adapter_exists,
        "model_mode": mode,
        "model_label": label
    }

# Route accessible from both /api/model-status (via apiClient) and /api/v1/model-status (legacy)
@app.get("/api/model-status")
def model_status():
    return _get_model_status_data()

@app.get("/api/v1/model-status")
def model_status_v1():
    return _get_model_status_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
