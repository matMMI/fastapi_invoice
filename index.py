"""Vercel serverless function entry point."""
from main import app

# Vercel requires the ASGI app to be exported
# The app is already configured in main.py with all routes and middleware
