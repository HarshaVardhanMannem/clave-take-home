"""
Vercel Serverless Function Entry Point
Wraps the FastAPI application for Vercel deployment

Vercel supports ASGI applications directly, so we just need to export the app.
The lifespan events will be handled automatically by Vercel's runtime.
"""
import sys
import os

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, backend_path)

# Import the FastAPI app
# Vercel will handle the ASGI application automatically
from backend.main import app

# Export the app for Vercel
# Vercel's Python runtime automatically detects and handles ASGI apps
handler = app

