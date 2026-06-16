#!/bin/bash
# Run E2E tests for Anvil Web UI

set -e

echo "🚀 Starting Anvil server..."

# Start the server in the background
cd /tmp/anvil_gh/anvil
python3 -m anvil.web.server &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 5

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Server failed to start"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

echo "✅ Server started successfully"

# Run E2E tests
echo "🧪 Running E2E tests..."
cd /tmp/anvil_gh/anvil
python3 -m pytest tests/test_e2e.py -v --browser chromium

# Capture exit code
EXIT_CODE=$?

# Stop the server
echo "🛑 Stopping server..."
kill $SERVER_PID 2>/dev/null || true

# Exit with test result
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All E2E tests passed!"
else
    echo "❌ Some E2E tests failed"
fi

exit $EXIT_CODE
