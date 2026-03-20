"""Simple web server to serve generated gazette HTML files."""

import os
from pathlib import Path
from aiohttp import web

OUTPUT_DIR = Path("/app/output")


async def index(request):
    """List all generated gazettes, newest first."""
    files = sorted(OUTPUT_DIR.glob("chronicle-*.html"), reverse=True)

    if not files:
        return web.Response(
            text="<html><body><h1>The Shipping Gazette</h1>"
            "<p>Noch keine Ausgaben generiert. Komm Montag wieder!</p>"
            "</body></html>",
            content_type="text/html",
        )

    # Redirect to latest
    latest = files[0].name
    raise web.HTTPFound(f"/{latest}")


async def serve_file(request):
    """Serve a specific gazette HTML file."""
    filename = request.match_info["filename"]
    filepath = OUTPUT_DIR / filename

    if not filepath.exists() or not filepath.name.startswith("chronicle-"):
        raise web.HTTPNotFound()

    return web.FileResponse(filepath)


async def archive(request):
    """List all editions as a simple HTML page."""
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


app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/archiv", archive)
app.router.add_get("/{filename}", serve_file)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
