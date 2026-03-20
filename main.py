"""The Shipping Gazette - CLI entry point."""

import argparse
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import (
    CHRONICLE_TAGLINE,
    CHRONICLE_TITLE,
    DAYS_BACK,
    OUTPUT_DIR,
)
from collector import collect_week_data, format_for_llm
from generator import generate_chronicle


def html_to_pdf(html_path: Path, pdf_path: Path):
    """Convert HTML file to PDF using Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{html_path.resolve()}")
        page.pdf(
            path=str(pdf_path),
            format="A3",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()


def get_week_range() -> str:
    """Get a formatted week range string."""
    end = datetime.now()
    start = end - timedelta(days=DAYS_BACK)
    return f"Woche vom {start.strftime('%d.%m.')} – {end.strftime('%d.%m.%Y')}"


def get_volume_info() -> str:
    """Generate volume/issue info based on current week."""
    now = datetime.now()
    week_num = now.isocalendar()[1]
    year = now.year
    return f"Jahrgang {year}, Ausgabe {week_num}"


def render_html(data: dict, title_override: str = None, tagline_override: str = None) -> str:
    """Render the newspaper HTML from template and generated data."""
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template.html")

    context = {
        "title": title_override or CHRONICLE_TITLE,
        "tagline": tagline_override or CHRONICLE_TAGLINE,
        "week_range": get_week_range(),
        "volume_info": get_volume_info(),
        "generated_at": datetime.now().strftime("%d.%m.%Y, %H:%M"),
        **data,
    }

    return template.render(**context)


def main():
    parser = argparse.ArgumentParser(description="The Shipping Gazette - Deine Wochenzeitung")
    parser.add_argument("--days", type=int, default=DAYS_BACK, help=f"Tage zurück (default: {DAYS_BACK})")
    parser.add_argument("--collect-only", action="store_true", help="Nur Daten sammeln, nicht generieren")
    parser.add_argument("--no-open", action="store_true", help="Browser nicht automatisch öffnen")
    parser.add_argument("--pdf", action="store_true", help="Zusätzlich PDF generieren")
    parser.add_argument("--source", choices=["all", "bitbucket", "github"], default="all", help="Nur Repos von dieser Quelle (default: all)")
    parser.add_argument("--team", action="store_true", help="NETNODE Team-Edition (Bitbucket, alle Autoren)")
    args = parser.parse_args()

    # Team mode forces bitbucket source
    if args.team:
        args.source = "bitbucket"

    # Override days if specified
    if args.days != DAYS_BACK:
        import config
        config.DAYS_BACK = args.days

    # Step 1: Collect git data
    source_label = {"all": "alle", "bitbucket": "Bitbucket", "github": "GitHub"}[args.source]
    edition = "NETNODE Team-Edition" if args.team else "Persönliche Edition"
    print(f"📡 Scanne Git-Repos ({source_label}, {edition})...")
    summaries = collect_week_data()

    # Filter by source
    if args.source != "all":
        summaries = [s for s in summaries if s.source == args.source]

    if not summaries:
        print(f"❌ Keine Commits in den letzten {args.days} Tagen gefunden.")
        sys.exit(1)

    activity_data = format_for_llm(summaries, team_mode=args.team)
    total_commits = sum(len(s.commits) for s in summaries)
    print(f"✅ {total_commits} Commits in {len(summaries)} Repos gefunden")

    if args.collect_only:
        print("\n" + activity_data)
        return

    # Step 2: Generate newspaper content
    print("✍️  Generiere Zeitungsartikel...")
    chronicle_data = generate_chronicle(activity_data, team_mode=args.team)
    print("✅ Artikel generiert")

    # Step 3: Render HTML
    print("🖨️  Rendere Zeitung...")
    title = "NETNODE Shipping Gazette" if args.team else CHRONICLE_TITLE
    tagline = "Was das Team diese Woche geschippt hat" if args.team else CHRONICLE_TAGLINE
    html = render_html(chronicle_data, title_override=title, tagline_override=tagline)

    # Step 4: Save output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    suffix = "-netnode" if args.team else (f"-{args.source}" if args.source != "all" else "")
    output_file = OUTPUT_DIR / f"chronicle-{date_str}{suffix}.html"
    output_file.write_text(html, encoding="utf-8")
    print(f"✅ Gespeichert: {output_file}")

    # Step 5: Generate PDF
    if args.pdf:
        print("📄 Generiere PDF...")
        pdf_file = OUTPUT_DIR / f"chronicle-{date_str}{suffix}.pdf"
        html_to_pdf(output_file, pdf_file)
        print(f"✅ PDF gespeichert: {pdf_file}")

    # Step 6: Open in browser
    if not args.no_open:
        open_file = (OUTPUT_DIR / f"chronicle-{date_str}{suffix}.pdf") if args.pdf else output_file
        webbrowser.open(f"file://{open_file.resolve()}")
        print("🌐 Im Browser geöffnet")


if __name__ == "__main__":
    main()
