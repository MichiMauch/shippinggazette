#!/bin/sh
# Pass environment variables to cron
env | grep -E '^(OPENAI_|GITHUB_|BITBUCKET_|CHRONICLE_|PORT=)' > /app/.env.cron

# Create cron job that sources env vars
echo "0 5 * * 1 cd /app && export \$(cat /app/.env.cron | xargs) && python main.py --api --no-open >> /var/log/gazette.log 2>&1" > /etc/cron.d/gazette
chmod 0644 /etc/cron.d/gazette
crontab /etc/cron.d/gazette

# Generate first edition on startup if none exists
if [ -z "$(ls /app/output/chronicle-*.html 2>/dev/null)" ]; then
    echo "No gazette found, generating first edition..."
    python main.py --api --no-open || true
fi

# Start cron + web server
cron
exec python server.py
