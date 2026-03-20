#!/bin/sh
echo "=== Shipping Gazette Container Starting ==="
mkdir -p /app/output

# Generate first edition on startup if none exists
if [ -z "$(ls /app/output/chronicle-*.html 2>/dev/null)" ]; then
    echo "=== Generating first edition ==="
    python main.py --api --no-open || echo "=== Generation failed, starting server anyway ==="
fi

echo "=== Starting web server ==="
exec python server.py
