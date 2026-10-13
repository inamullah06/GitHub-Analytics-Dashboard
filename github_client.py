"""Thin wrapper around the GitHub REST API for public profile and repository data."""

from __future__ import annotations

import re
from typing import Any

import requests

API_BASE = "https://api.github.com"
PER_PAGE = 100  # GitHub's maximum page size
TIMEOUT_SECONDS = 15

# GitHub usernames: alphanumerics and single hyphens, up to 39 characters.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


class GitHubAPIError(Exception):
    """Raised for any failed GitHub API call, with a message safe to show users."""


def validate_username(username: str) -> str:
    """Return the stripped username, or raise GitHubAPIError if it is malformed."""
    cleaned = (username or "").strip()
    if not _USERNAME_RE.match(cleaned):
        raise GitHubAPIError(
            "Invalid GitHub username. Use letters, digits and single hyphens (max 39 characters)."
        )
    return cleaned


class GitHubClient:
    def __init__(self, token: str | None = None, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-analytics-dashboard",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        try:
            response = self.session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise GitHubAPIError(f"Network error contacting GitHub: {exc}") from exc

        if response.status_code == 404:
            raise GitHubAPIError("GitHub user not found.")
        if response.status_code in (403, 429) and response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubAPIError(
                "GitHub rate limit reached. Add a personal access token in the sidebar or try again later."
            )
        if not response.ok:
            raise GitHubAPIError(f"GitHub API error {response.status_code}.")
        return response

    def get_user(self, username: str) -> dict[str, Any]:
        """Return the public profile for a user."""
        username = validate_username(username)
        return self._get(f"{API_BASE}/users/{username}").json()

    def get_repos(self, username: str) -> list[dict[str, Any]]:
        """Return every public repository owned by the user, following pagination."""
        username = validate_username(username)
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._get(
                f"{API_BASE}/users/{username}/repos",
                params={"type": "owner", "sort": "updated", "per_page": PER_PAGE, "page": page},
            )
            batch = response.json()
            repos.extend(batch)
            if len(batch) < PER_PAGE:
                break
            page += 1
        return repos
