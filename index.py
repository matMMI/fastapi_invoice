import os
import sys

# Add the current directory to sys.path to ensure local modules can be imported
# This handles cases where Vercel might set the CWD differently
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api.main import app
except ImportError:
    # Fallback if 'api' package is not resolved (e.g. if CWD is inside api/)
    from main import app
