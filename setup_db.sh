#!/bin/bash

# Database setup script - Automated initialization
# Usage: ./setup_db.sh

set -e

echo "=========================================="
echo "🚀 Devis Generator - Database Setup"
echo "=========================================="
echo ""

# SAFETY: Check environment
if [ "$ENVIRONMENT" = "production" ] || grep -q 'ENVIRONMENT=production' .env.local 2>/dev/null; then
    echo "❌ DANGER: Cannot run database setup in production!"
    echo "   This script is for development only."
    echo "   Make sure ENVIRONMENT=development in .env.local"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please create it first:"
    echo "   python3 -m venv venv"
    exit 1
fi

# Activate venv
source venv/bin/activate

echo "0️⃣  Installing dependencies..."
pip install -q -e . 2>/dev/null || pip install -q -r requirements.txt 2>/dev/null || true
echo "✅ Dependencies checked"
echo ""

echo "1️⃣  Running database migrations..."
echo "   (Creating tables, indexes, enums...)"
python run_migrations.py
if [ $? -ne 0 ]; then
    echo "❌ Migrations failed!"
    exit 1
fi
echo "✅ Migrations complete"
echo ""

echo "2️⃣  Resetting database and creating admin user..."
echo "   (User: $ADMIN_USERNAME, Email: $ADMIN_EMAIL)"
python reset_db.py
if [ $? -ne 0 ]; then
    echo "❌ Database reset failed!"
    exit 1
fi
echo "✅ Admin user created"
echo ""

echo "3️⃣  Seeding additional test data..."
./seed.sh
if [ $? -ne 0 ]; then
    echo "❌ Seeding failed!"
    exit 1
fi
echo "✅ Seed data added"
echo ""

echo "=========================================="
echo "✨ Database setup complete!"
echo "=========================================="
echo ""
echo "📝 Summary:"
echo "   • Migrations: Applied"
echo "   • Database: Reset and initialized"
echo "   • Admin user: Created"
echo "   • Test data: Seeded"
echo ""
echo "🎯 Next steps:"
echo "   1. Start the backend:  python main.py"
echo "   2. Start the frontend: cd ../devis_generator && pnpm dev"
echo "   3. Login with:"
echo "      Username: $ADMIN_USERNAME"
echo "      Password: $ADMIN_PASSWORD"
echo ""
