"""Configuration for The Shipping Gazette."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Base directory to scan for git repos
REPOS_BASE_DIR = Path(os.getenv("CHRONICLE_REPOS_DIR", "/Users/michaelmauch/Documents/Development"))

# Output directory
OUTPUT_DIR = Path(__file__).parent / "output"

# How many days back to collect commits
DAYS_BACK = int(os.getenv("CHRONICLE_DAYS_BACK", "7"))

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("CHRONICLE_MODEL", "gpt-4.1")

# Repos to exclude from scanning
EXCLUDE_REPOS = {
    "chronicle",  # this project itself
    "node_modules",
    ".git",
}

# Minimum commits for a repo to appear in the chronicle
MIN_COMMITS = 1

# Newspaper settings
CHRONICLE_TITLE = "The Shipping Gazette"
CHRONICLE_TAGLINE = "Wöchentlich frisch deployt"
AUTHOR_NAME = os.getenv("CHRONICLE_AUTHOR", "Michael Mauch")
