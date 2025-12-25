#!/bin/bash
# Database Seeder Script
# Usage: ./seed.sh [--clients N] [--quotes N]
#
# Generates fake data for testing purposes.
# Automatically detects the first user in the database.

set -e

# Default values
CLIENTS=30
QUOTES=200

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --clients) CLIENTS="$2"; shift ;;
        --quotes) QUOTES="$2"; shift ;;
        -h|--help)
            echo "Usage: ./seed.sh [--clients N] [--quotes N]"
            echo ""
            echo "Options:"
            echo "  --clients N    Number of clients to create (default: 30)"
            echo "  --quotes N     Number of quotes to create (default: 200)"
            echo ""
            echo "Example: ./seed.sh --clients 50 --quotes 300"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔍 Fetching user ID from database..."

# Get the first user ID from the database
USER_ID=$(./venv/bin/python -c "
from db.session import engine
from sqlmodel import Session, select
from models.user import User
with Session(engine) as session:
    user = session.exec(select(User)).first()
    if user:
        print(user.id)
    else:
        print('NO_USER')
")

if [ "$USER_ID" = "NO_USER" ] || [ -z "$USER_ID" ]; then
    echo "❌ Error: No user found in the database."
    echo "   Please create a user account first by signing up in the app."
    exit 1
fi

echo "✅ Found user: $USER_ID"
echo ""

# Run the seeder
./venv/bin/python seed_data.py --user-id "$USER_ID" --clients "$CLIENTS" --quotes "$QUOTES"
