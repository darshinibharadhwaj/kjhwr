import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app import app  # Vercel serves `app` (WSGI)
