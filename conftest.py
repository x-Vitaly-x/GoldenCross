# Set dummy env vars before any module imports so config.py doesn't fail in tests.
# Real .env values take precedence via setdefault.
import os

os.environ.setdefault("T212_API_KEY", "test_key")
os.environ.setdefault("T212_SECRET_KEY", "test_secret")
os.environ.setdefault("T212_MODE", "demo")
os.environ.setdefault("TOGETHER_API_KEY", "test_together_key")
