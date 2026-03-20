"""Web server + scheduler for The Shipping Gazette."""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web

OUTPUT_DIR = Path(os.getenv("GAZETTE_OUTPUT_DIR", "/app/output"))


async def index(request):
    """Redirect to latest gazette."""
    files = sorted(OUTPUT_DIR.glob("chronicle-*.html"), reverse=True)

    if not files:
        return web.Response(
            text="<html><body><h1>The Shipping Gazette</h1>"
            "<p>Noch keine Ausgaben generiert. Komm Montag wieder!</p>"
            "</body></html>",
            content_type="text/html",
        )

    raise web.HTTPFound(f"/{files[0].name}")


async def serve_file(request):
    """Serve a specific gazette HTML file."""
    filename = request.match_info["filename"]
    filepath = OUTPUT_DIR / filename

    if not filepath.exists() or not filepath.name.startswith("chronicle-"):
        raise web.HTTPNotFound()

    return web.FileResponse(filepath)


async def archive(request):
    """List all editions."""
    files = sorted(OUTPUT_DIR.glob("chronicle-*.html"), reverse=True)
    items = "\n".join(
        f'<li><a href="/{f.name}">{f.stem}</a></li>' for f in files
    )
    html = f"""<html>
<head><title>Archiv — The Shipping Gazette</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px}}
a{{color:#6366f1}}</style></head>
<body><h1>Archiv</h1><ul>{items}</ul></body></html>"""
    return web.Response(text=html, content_type="text/html")


async def scheduler():
    """Run gazette generation every Monday at 05:00 UTC (06:00 CET)."""
    while True:
        now = datetime.now(timezone.utc)
        # Next Monday at 05:00 UTC
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0 and now.hour >= 5:
            days_until_monday = 7
        next_run = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
        wait_seconds = (next_run - now).total_seconds()
        print(f"⏰ Nächste Gazette: {next_run.strftime('%A %d.%m.%Y %H:%M UTC')} (in {wait_seconds/3600:.1f}h)")

        await asyncio.sleep(wait_seconds)

        print("⏰ Scheduled generation starting...")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "main.py", "--api", "--no-open",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            print(stdout.decode())
            if proc.returncode == 0:
                print("✅ Scheduled generation complete")
            else:
                print(f"❌ Scheduled generation failed (exit {proc.returncode})")
        except Exception as e:
            print(f"❌ Scheduler error: {e}")


async def generate(request):
    """Manually trigger gazette generation."""
    secret = os.getenv("GENERATE_SECRET", "")
    if secret and request.query.get("secret") != secret:
        raise web.HTTPForbidden(text="Invalid secret")

    print("🔄 Manual generation triggered...")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "main.py", "--api", "--no-open",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        print(output)
        if proc.returncode == 0:
            return web.Response(text=f"✅ Gazette generiert!\n\n{output}", content_type="text/plain")
        return web.Response(text=f"❌ Fehler (exit {proc.returncode})\n\n{output}", content_type="text/plain", status=500)
    except Exception as e:
        return web.Response(text=f"❌ Error: {e}", content_type="text/plain", status=500)


async def start_scheduler(app):
    app["scheduler"] = asyncio.create_task(scheduler())


async def stop_scheduler(app):
    app["scheduler"].cancel()


app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/archiv", archive)
app.router.add_get("/generate", generate)
app.router.add_get("/{filename}", serve_file)
app.on_startup.append(start_scheduler)
app.on_cleanup.append(stop_scheduler)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
