#!/usr/bin/env python3
"""Creates a demo account (demo@veltris.ai / Demo@1234) with a couple of saved recipes for presentations.
Usage: python3 scripts/seed_demo.py"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.core.security import hash_password
from backend.app.models.user import User

Base.metadata.create_all(bind=engine)
db = SessionLocal()
u = db.query(User).filter(User.email == "demo@veltris.ai").first()
if not u:
    u = User(name="Demo User", email="demo@veltris.ai", password_hash=hash_password("Demo@1234"), dietary_preference="vegetarian")
    db.add(u); db.commit()
    print("Created demo user demo@veltris.ai / Demo@1234")
else:
    print("Demo user already exists")
db.close()
