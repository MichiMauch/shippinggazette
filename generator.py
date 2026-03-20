"""LLM-based newspaper article generator."""

import json
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, CHRONICLE_TITLE, AUTHOR_NAME, DAYS_BACK

client = OpenAI(api_key=OPENAI_API_KEY)

STYLE_RULES = """Schreibe auf Deutsch, im Stil einer seriösen Zeitung aber mit einem Augenzwinkern.
Verwende Zeitungsjargon: "Quellen berichten...", "Insider bestätigen...", "Exklusiv:", etc.

WICHTIG:
- Gib NUR valides JSON zurück, keine Markdown-Codeblöcke, kein anderer Text.
- Verwende ausschliesslich Schweizer Rechtschreibung (kein ß, immer ss). Beispiel: "grosse" statt "große", "strasse" statt "straße"."""

PERSONAL_SYSTEM_PROMPT = f"""Du bist ein humorvoller Tech-Journalist der "{CHRONICLE_TITLE}" schreibt.
Du verwandelst Git-Commit-Daten in unterhaltsame, zeitungsartige Artikel über die Entwicklungswoche von {AUTHOR_NAME}.

{STYLE_RULES}"""

TEAM_SYSTEM_PROMPT = f"""Du bist ein humorvoller Tech-Journalist der "NETNODE Shipping Gazette" schreibt.
Du verwandelst Git-Commit-Daten in unterhaltsame, zeitungsartige Artikel über die Arbeitswoche des NETNODE-Teams.
Hebe die Beiträge der einzelnen Teammitglieder hervor. Erwähne wer was gemacht hat.

{STYLE_RULES}"""

GENERATION_PROMPT = """Analysiere die folgende Entwicklungsaktivität und erstelle eine Zeitungsausgabe.

{activity_data}

Erstelle ein JSON-Objekt mit dieser Struktur:
{{
  "headline_title": "Grosse Schlagzeile über das wichtigste Projekt/Achievement der Woche",
  "headline_byline": "Kurze Autorenzeile mit Datum",
  "headline_text": "2-3 Absätze im Zeitungsstil über das Hauptthema. Unterhaltsam, informativ.",
  "headline_quote": "Ein witziges Zitat passend zum Hauptthema",
  "headline_quote_attribution": "— Witzige Quellenangabe",
  "sidebar_highlights": [
    {{"label": "Kategorie", "text": "Kurze Beschreibung"}},
  ],
  "project_articles": [
    {{
      "title": "Projektname oder kreative Überschrift",
      "text": "1-2 Absätze über die Aktivitäten in diesem Projekt"
    }},
  ],
  "code_learnings_title": "Kreative Überschrift für Code & Learnings",
  "code_learnings_text": "1-2 Absätze über technische Erkenntnisse der Woche, abgeleitet aus den Commits",
  "looking_ahead_text": "1-2 Absätze Ausblick auf die nächste Woche basierend auf den aktuellen Trends",
  "looking_ahead_quote": "Motivierendes oder lustiges Abschlusszitat",
  "looking_ahead_quote_attribution": "— Quellenangabe",
  "stats": {{
    "total_commits": 0,
    "total_repos": 0,
    "total_insertions": 0,
    "total_deletions": 0,
    "most_active_repo": "name",
    "busiest_day": "Montag"
  }}
}}

Regeln:
- sidebar_highlights: genau 5 Einträge
- project_articles: 3-6 Einträge (die aktivsten/interessantesten Projekte)
- Schreibe auf Deutsch in Schweizer Rechtschreibung (kein ß, immer ss)
- Sei kreativ und unterhaltsam, aber basiere alles auf den echten Daten
- stats müssen auf den echten Zahlen basieren
"""


def generate_chronicle(activity_data: str, team_mode: bool = False) -> dict:
    """Generate newspaper content from activity data using OpenAI."""
    system_prompt = TEAM_SYSTEM_PROMPT if team_mode else PERSONAL_SYSTEM_PROMPT
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": GENERATION_PROMPT.format(activity_data=activity_data)},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    content = response.choices[0].message.content
    return json.loads(content)
