"""Git data collector - scans repos and collects commits from the past week."""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from config import REPOS_BASE_DIR, DAYS_BACK, EXCLUDE_REPOS, MIN_COMMITS


@dataclass
class Commit:
    hash: str
    author: str
    date: str
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class RepoSummary:
    name: str
    path: Path
    commits: list[Commit] = field(default_factory=list)
    remote_url: str = ""
    source: str = ""  # "github" or "bitbucket" or "unknown"

    @property
    def total_files_changed(self) -> int:
        return sum(c.files_changed for c in self.commits)

    @property
    def total_insertions(self) -> int:
        return sum(c.insertions for c in self.commits)

    @property
    def total_deletions(self) -> int:
        return sum(c.deletions for c in self.commits)


def detect_source(remote_url: str) -> str:
    """Detect if repo is GitHub or Bitbucket based on remote URL."""
    if "github.com" in remote_url:
        return "github"
    if "bitbucket.org" in remote_url:
        return "bitbucket"
    return "unknown"


def get_remote_url(repo_path: Path) -> str:
    """Get the remote origin URL of a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def get_commits(repo_path: Path, since_date: str) -> list[Commit]:
    """Get commits from a repo since a given date."""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path), "log",
                f"--since={since_date}",
                "--format=%H|%an|%ai|%s",
                "--shortstat",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []

        commits = []
        lines = result.stdout.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            if "|" in line and len(line.split("|")) >= 4:
                parts = line.split("|", 3)
                commit = Commit(
                    hash=parts[0],
                    author=parts[1],
                    date=parts[2],
                    message=parts[3],
                )
                # Check next line for stats
                if i + 1 < len(lines):
                    stat_line = lines[i + 1].strip()
                    if "file" in stat_line:
                        # Parse "3 files changed, 45 insertions(+), 12 deletions(-)"
                        import re
                        files_m = re.search(r"(\d+) file", stat_line)
                        ins_m = re.search(r"(\d+) insertion", stat_line)
                        del_m = re.search(r"(\d+) deletion", stat_line)
                        commit.files_changed = int(files_m.group(1)) if files_m else 0
                        commit.insertions = int(ins_m.group(1)) if ins_m else 0
                        commit.deletions = int(del_m.group(1)) if del_m else 0
                        i += 1
                commits.append(commit)
            i += 1

        return commits
    except (subprocess.TimeoutExpired, Exception):
        return []


def find_repos(base_dir: Path) -> list[Path]:
    """Find all git repositories in the base directory (one level deep)."""
    repos = []
    if not base_dir.is_dir():
        return repos

    for entry in sorted(base_dir.iterdir()):
        if entry.name in EXCLUDE_REPOS:
            continue
        if entry.is_dir() and (entry / ".git").is_dir():
            repos.append(entry)

    return repos


def collect_week_data() -> list[RepoSummary]:
    """Collect git data from all repos for the past week."""
    since_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    repos = find_repos(REPOS_BASE_DIR)

    summaries = []
    for repo_path in repos:
        commits = get_commits(repo_path, since_date)
        if len(commits) < MIN_COMMITS:
            continue

        remote_url = get_remote_url(repo_path)
        summary = RepoSummary(
            name=repo_path.name,
            path=repo_path,
            commits=commits,
            remote_url=remote_url,
            source=detect_source(remote_url),
        )
        summaries.append(summary)

    # Sort by number of commits descending
    summaries.sort(key=lambda s: len(s.commits), reverse=True)
    return summaries


def format_for_llm(summaries: list[RepoSummary], team_mode: bool = False) -> str:
    """Format collected data as text for the LLM prompt."""
    total_commits = sum(len(s.commits) for s in summaries)
    total_repos = len(summaries)

    # Collect unique authors
    all_authors = set()
    for s in summaries:
        for c in s.commits:
            all_authors.add(c.author)

    lines = [
        f"DEVELOPMENT ACTIVITY SUMMARY ({DAYS_BACK} days)",
        f"Total: {total_commits} commits across {total_repos} repos",
    ]

    if team_mode:
        lines.append(f"Team: {', '.join(sorted(all_authors))}")
    else:
        from config import AUTHOR_NAME
        lines.append(f"Developer: {AUTHOR_NAME}")

    lines.append("")

    for summary in summaries:
        source_tag = f" [{summary.source}]" if summary.source != "unknown" else ""
        lines.append(f"## {summary.name}{source_tag}")
        lines.append(
            f"   {len(summary.commits)} commits | "
            f"+{summary.total_insertions} -{summary.total_deletions} lines | "
            f"{summary.total_files_changed} files changed"
        )

        for commit in summary.commits:
            date_short = commit.date[:10]
            if team_mode:
                lines.append(f"   - [{date_short}] ({commit.author}) {commit.message}")
            else:
                lines.append(f"   - [{date_short}] {commit.message}")

        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    summaries = collect_week_data()
    print(format_for_llm(summaries))
