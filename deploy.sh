#!/bin/bash
set -e # Exit on any error

PROJECT_DIR="/Users/louis-philippedavid/Sites/finance_agent"
cd "$PROJECT_DIR"

echo "📥 Pulling latest code..."
git pull

echo "🐍 Updating Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt --quiet

echo "🗄️ Running migrations..."
python manage.py migrate --settings=finance_backend.settings.remote

echo "⚛️ Building Frontend..."
cd frontend
npm install --silent
npm run build
cd ..

echo "🚀 Restarting services (launchd)..."
# Unload and Reload to ensure fresh environment variables and code
# Note: These paths assume you have moved the .plist files to ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.finance.gunicorn.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.finance.gunicorn.plist

launchctl unload ~/Library/LaunchAgents/com.finance.celery.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.finance.celery.plist

echo "✅ Deploy complete"
