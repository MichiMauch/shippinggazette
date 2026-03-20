"""API-based git data collector - fetches commits from GitHub and Bitbucket APIs."""

import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from config import DAYS_BACK, MIN_COMMITS


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
    commits: list[Commit] = field(default_factory=list)
    source: str = ""  # "github" or "bitbucket"

    @property
    def total_files_changed(self) -> int:
        return sum(c.files_changed for c in self.commits)

    @property
    def total_insertions(self) -> int:
        return sum(c.insertions for c in self.commits)

    @property
    def total_deletions(self) -> int:
        return sum(c.deletions for c in self.commits)


def fetch_github_commits(username: str, token: str, since_date: str) -> list[RepoSummary]:
    """Fetch commits from all GitHub repos for a user."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    summaries = []

    # List all repos (paginated)
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/user/repos",
            headers=headers,
            params={"per_page": 100, "page": page, "sort": "pushed", "direction": "desc"},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        # Stop early: if the last repo was pushed before our window, no need to paginate further
        if batch[-1].get("pushed_at", "") < since_date:
            break
        page += 1

    for repo in repos:
        repo_name = repo["full_name"]
        pushed_at = repo.get("pushed_at", "")
        if pushed_at < since_date:
            continue

        # Fetch commits (no author filter — GitHub API only matches linked accounts)
        resp = requests.get(
            f"https://api.github.com/repos/{repo_name}/commits",
            headers=headers,
            params={"since": since_date, "per_page": 100},
            timeout=15,
        )
        if resp.status_code != 200:
            continue

        commits_data = resp.json()

        # Filter by author name locally
        from config import AUTHOR_NAME, AUTHOR_ALIASES
        all_names = [AUTHOR_NAME] + AUTHOR_ALIASES
        commits = []
        for c in commits_data:
            commit_info = c.get("commit", {})
            author_info = commit_info.get("author", {})
            author_name = author_info.get("name", "unknown")

            if not any(n.lower() in author_name.lower() or author_name.lower() in n.lower() for n in all_names):
                continue

            commits.append(Commit(
                hash=c.get("sha", "")[:8],
                author=author_name,
                date=author_info.get("date", "")[:10],
                message=commit_info.get("message", "").split("\n")[0],
            ))

        summaries.append(RepoSummary(
            name=repo["name"],
            commits=commits,
            source="github",
        ))

    return summaries


def fetch_bitbucket_commits(workspace: str, api_key: str, since_date: str, username: str = "", author_filter: str = "") -> list[RepoSummary]:
    """Fetch commits from all Bitbucket repos in a workspace."""
    # Atlassian API tokens use Basic Auth (email:token)
    if username:
        auth = (username, api_key)
        headers = {"Accept": "application/json"}
    else:
        auth = None
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    summaries = []

    # List all repos in workspace (paginated)
    repos = []
    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}"
    params = {"pagelen": 100, "sort": "-updated_on"}
    while url:
        resp = requests.get(url, headers=headers, auth=auth, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        repos.extend(data.get("values", []))
        url = data.get("next")
        params = {}  # next URL already contains params
        # Stop if repos are older than our window
        if data.get("values") and data["values"][-1].get("updated_on", "") < since_date:
            break

    for repo in repos:
        repo_slug = repo["slug"]
        updated_on = repo.get("updated_on", "")
        if updated_on < since_date:
            continue

        # Fetch commits
        commits_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/commits"
        all_commits = []
        page_url = commits_url
        page_params = {"pagelen": 100}

        while page_url:
            resp = requests.get(page_url, headers=headers, auth=auth, params=page_params, timeout=15)
            if resp.status_code != 200:
                break

            data = resp.json()
            for c in data.get("values", []):
                commit_date = c.get("date", "")[:10]
                if commit_date < since_date:
                    page_url = None
                    break

                author_raw = c.get("author", {})
                author_name = author_raw.get("user", {}).get("display_name", "")
                if not author_name:
                    author_name = author_raw.get("raw", "unknown").split("<")[0].strip()

                # Filter by author if specified (personal mode)
                # Match any part of the name (e.g. "Michael Mauch" matches "Michi Mauch")
                if author_filter and not any(
                    part.lower() in author_name.lower()
                    for part in author_filter.split()
                ):
                    continue

                all_commits.append(Commit(
                    hash=c.get("hash", "")[:8],
                    author=author_name,
                    date=commit_date,
                    message=c.get("message", "").split("\n")[0],
                ))
            else:
                page_url = data.get("next")
                page_params = {}

        if len(all_commits) < MIN_COMMITS:
            continue

        summaries.append(RepoSummary(
            name=repo["name"],
            commits=all_commits,
            source="bitbucket",
        ))

    return summaries


def collect_api_data(
    github_username: str = "",
    github_token: str = "",
    bitbucket_workspace: str = "",
    bitbucket_api_key: str = "",
    bitbucket_username: str = "",
    source_filter: str = "all",
    team_mode: bool = False,
) -> list[RepoSummary]:
    """Collect commits from GitHub and/or Bitbucket APIs."""
    since_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT00:00:00Z")
    summaries = []

    # In personal mode, filter Bitbucket commits to only the user's
    from config import AUTHOR_NAME
    author_filter = "" if team_mode else AUTHOR_NAME

    if source_filter in ("all", "github") and github_token and github_username:
        print(f"  📡 GitHub: Lade Repos für {github_username}...")
        try:
            gh = fetch_github_commits(github_username, github_token, since_date)
            print(f"  ✅ GitHub: {sum(len(s.commits) for s in gh)} Commits in {len(gh)} Repos")
            summaries.extend(gh)
        except Exception as e:
            print(f"  ❌ GitHub Fehler: {e}")

    if source_filter in ("all", "bitbucket") and bitbucket_api_key and bitbucket_workspace:
        print(f"  📡 Bitbucket: Lade Repos für {bitbucket_workspace}...")
        try:
            bb = fetch_bitbucket_commits(bitbucket_workspace, bitbucket_api_key, since_date, username=bitbucket_username, author_filter=author_filter)
            print(f"  ✅ Bitbucket: {sum(len(s.commits) for s in bb)} Commits in {len(bb)} Repos")
            summaries.extend(bb)
        except Exception as e:
            print(f"  ❌ Bitbucket Fehler: {e}")

    summaries.sort(key=lambda s: len(s.commits), reverse=True)
    return summaries


def format_for_llm(summaries: list[RepoSummary], team_mode: bool = False) -> str:
    """Format collected data as text for the LLM prompt."""
    total_commits = sum(len(s.commits) for s in summaries)
    total_repos = len(summaries)

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
        source_tag = f" [{summary.source}]" if summary.source else ""
        lines.append(f"## {summary.name}{source_tag}")
        lines.append(
            f"   {len(summary.commits)} commits | "
            f"+{summary.total_insertions} -{summary.total_deletions} lines | "
            f"{summary.total_files_changed} files changed"
        )

        for commit in summary.commits:
            if team_mode:
                lines.append(f"   - [{commit.date}] ({commit.author}) {commit.message}")
            else:
                lines.append(f"   - [{commit.date}] {commit.message}")

        lines.append("")

    return "\n".join(lines)
