#!/bin/bash
# Deploy latest dashboard changes (rebuild frontend + restart service)
set -e

cd "$(dirname "$0")/.."

echo "📦 Building frontend..."
npx vite build

echo "🔄 Restarting service..."
systemctl --user restart lodekeeper-dash.service

sleep 2

if systemctl --user is-active --quiet lodekeeper-dash.service; then
  echo "✅ Dashboard deployed and running on port 7777"
else
  echo "❌ Service failed to start"
  systemctl --user status lodekeeper-dash.service
  exit 1
fi
