#!/bin/sh

echo "=== Shipping Gazette Container Starting ==="

# Pass environment variables to cron
env | grep -E '^(OPENAI_|GITHUB_|BITBUCKET_|CHRONICLE_|PORT=)' > /app/.env.cron || true

# Setup cron if available
if command -v crontab >/dev/null 2>&1; then
    echo "0 5 * * 1 cd /app && export \$(cat /app/.env.cron | xargs) && python main.py --api --no-open >> /var/log/gazette.log 2>&1" > /etc/cron.d/gazette
    chmod 0644 /etc/cron.d/gazette
    crontab /etc/cron.d/gazette
    cron
    echo "=== Cron started ==="
else
    echo "=== WARNING: cron not found, skipping scheduled tasks ==="
fi

# Generate first edition on startup if none exists
if [ -z "$(ls /app/output/chronicle-*.html 2>/dev/null)" ]; then
    echo "=== No gazette found, generating first edition ==="
    python main.py --api --no-open || echo "=== Generation failed, starting server anyway ==="
fi

echo "=== Starting web server on port 8080 ==="
exec python server.py
