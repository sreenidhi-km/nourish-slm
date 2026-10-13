import os

# Keep unit/integration tests fast and deterministic: skip neural generation (retrieval + validator only).
os.environ.setdefault("SLM_GENERATE", "false")
os.environ.setdefault("ALLOW_DEMO_USER", "true")
