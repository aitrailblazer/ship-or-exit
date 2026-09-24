"""GitHub commit collector with bot/merge noise filtering.

Raw commit counts lie: merges, dependabot bumps, docs-only touch-ups,
and CI churn inflate them without representing engineering work. This
module fetches commits and keeps only human engineering activity.
"""
from __future__ import annotations

import os
import re
import time

import requests

API = "https://api.github.com"
BOT_SUFFIX = "[bot]"
BOT_NAMES = {"dependabot", "renovate", "github-actions",
             "dependabot[bot]", "renovate[bot]", "github-actions[bot]"}

# First line of the commit message is what these patterns see. They are
# deliberately message-first: the commits() collector does not fetch
# per-commit file lists, so filtering must work without them. When a
# "files" list IS present (e.g. in tests or a future enriched fetch),
# the path-based fallbacks below apply as well.
DOC_MESSAGE_RES = [
    re.compile(r"^\s*docs?(\(.+\))?\s*:", re.IGNORECASE),          # docs:, docs(api):
    re.compile(r"^\s*documentation\s*:", re.IGNORECASE),           # documentation:
    re.compile(r"^\s*wiki\s*:", re.IGNORECASE),                    # wiki:
    re.compile(r"\bupdate[sd]?\s+(the\s+)?(docs?|documentation|read\s?me)\b",
               re.IGNORECASE),
    re.compile(r"\bread\s?me\b", re.IGNORECASE),                   # README touch-ups
    re.compile(r"\b(docs?|documentation)[- ]only\b", re.IGNORECASE),
    re.compile(r"\btypo\b.*\b(docs?|read\s?me|comments?)\b", re.IGNORECASE),
    re.compile(r"\b(docs?|read\s?me|comments?)\b.*\btypo\b", re.IGNORECASE),
]

DEP_MESSAGE_RES = [
    re.compile(r"\bdependabot\b", re.IGNORECASE),
    re.compile(r"\brenovate\b", re.IGNORECASE),
    re.compile(r"\bbump\b", re.IGNORECASE),                        # Bump lodash ...
    re.compile(r"^\s*(chore|build|ci|deps)(\(.+\))?\s*:\s*(bump|update|upgrade)\b",
               re.IGNORECASE),                                     # chore(deps): bump
    re.compile(r"^\s*deps?(\(.+\))?\s*:", re.IGNORECASE),          # deps:, dep(api):
    re.compile(r"\bupdate[sd]?\s+(deps?|dependencies|lockfiles?|lock[ -]?files?)\b",
               re.IGNORECASE),
    re.compile(r"\bupgrade[sd]?\s+(deps?|dependencies)\b", re.IGNORECASE),
    re.compile(r"\b(automated\s+)?dependenc(y|ies)\s+(update|upgrade|bump)\b",
               re.IGNORECASE),
    re.compile(r"\b(lockfiles?|lock[ -]?files?)\s+(update|upgrade|bump)\b",
               re.IGNORECASE),
]

DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
DOC_FILENAMES = {"readme", "changelog", "changes", "contributing", "code_of_conduct"}
DOC_DIR_PREFIXES = ("docs/", "documentation/", "wiki/", ".github/ISSUE_TEMPLATE/")
LOCKFILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
                 "Cargo.lock", "Gemfile.lock", "poetry.lock", "Pipfile.lock",
                 "composer.lock", "go.sum", "flake.lock"}


class GitHubError(Exception):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None, max_pages: int = 5):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "ship-or-exit",
        })
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def _get(self, url, params):
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise GitHubError(
                "GitHub rate limit hit. Set GITHUB_TOKEN for 5,000 req/hr "
                "(unauthenticated limit is 60/hr).")
        if resp.status_code == 404:
            raise GitHubError(f"Repo not found: {url}")
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub HTTP {resp.status_code} on {url}: {resp.text[:200]}")
        return resp

    def commits(self, repo: str, since: str, until: str):
        """Raw commit dicts for owner/repo between ISO datetimes."""
        out: list = []
        url = f"{API}/repos/{repo}/commits"
        params: dict | None = {"since": since, "until": until, "per_page": 100}
        for _ in range(self.max_pages):
            resp = self._get(url, params)
            for item in resp.json():
                inner = item.get("commit", {}) or {}
                author = inner.get("author", {}) or {}
                gh_author = item.get("author") or {}
                out.append({
                    "sha": item.get("sha"),
                    "date": author.get("date"),
                    "author_login": gh_author.get("login"),
                    "author_name": author.get("name"),
                    "message": (inner.get("message") or "").split("\n")[0],
                    "is_merge": len(item.get("parents", [])) > 1,
                })
            nxt = _next_link(resp.headers.get("Link", ""))
            if not nxt:
                break
            url, params = nxt, None
            time.sleep(0.3)
        return [c for c in out if c.get("date")]


def _message(commit: dict) -> str:
    return (commit.get("message") or "").split("\n")[0].strip()


def _file_paths(commit: dict) -> list | None:
    """Normalized file paths, or None when the commit carries no file list."""
    files = commit.get("files")
    if not files:
        return None
    out = []
    for item in files:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            name = item.get("filename") or item.get("path")
            if name:
                out.append(name)
    return out or None


def _is_docs_path(path: str) -> bool:
    lowered = path.lower()
    base = lowered.rsplit("/", 1)[-1]
    stem, dot, _ext = base.partition(".")
    if dot and ("." + _ext) in DOC_EXTENSIONS:
        return True
    if stem in DOC_FILENAMES:
        return True
    return lowered.startswith(DOC_DIR_PREFIXES)


def is_docs_only(commit: dict) -> bool:
    """True when a commit only touches documentation.

    Message-first (the collector stores no file lists), with a path-based
    fallback: if a "files" list is present, every path must be docs.
    """
    if any(rx.search(_message(commit)) for rx in DOC_MESSAGE_RES):
        return True
    paths = _file_paths(commit)
    if paths is not None:
        return bool(paths) and all(_is_docs_path(p) for p in paths)
    return False


def is_dependency_bump(commit: dict) -> bool:
    """True for automated/manual dependency-bump commits.

    Message-first, with a path-based fallback: if a "files" list is
    present, a commit touching only lockfiles counts as a bump.
    """
    if any(rx.search(_message(commit)) for rx in DEP_MESSAGE_RES):
        return True
    paths = _file_paths(commit)
    if paths is not None:
        basenames = [p.rsplit("/", 1)[-1].lower() for p in paths]
        return bool(basenames) and all(b in LOCKFILENAMES for b in basenames)
    return False


def is_human(commit: dict) -> bool:
    """True for human engineering commits.

    False for merges, bots, documentation-only commits, and
    dependency-bump commits.
    """
    if commit.get("is_merge"):
        return False
    login = (commit.get("author_login") or "").lower()
    name = (commit.get("author_name") or "").lower()
    if login.endswith(BOT_SUFFIX) or login in BOT_NAMES or name in BOT_NAMES:
        return False
    if is_dependency_bump(commit):
        return False
    if is_docs_only(commit):
        return False
    return True


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None
