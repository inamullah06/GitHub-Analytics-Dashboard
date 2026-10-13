"""Pure data-processing functions. No network or UI code lives here so they are easy to test."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

UNKNOWN_LANGUAGE = "Unknown"

# Columns written to the CSV export, in order.
EXPORT_COLUMNS = [
    "name",
    "url",
    "description",
    "language",
    "stars",
    "forks",
    "open_issues",
    "fork",
    "archived",
    "created_at",
    "updated_at",
]


def repos_to_dataframe(repos: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Normalise raw GitHub repository objects into a typed DataFrame."""
    rows = []
    for repo in repos:
        rows.append(
            {
                "name": repo.get("name") or "",
                "url": repo.get("html_url") or "",
                "description": repo.get("description") or "",
                "language": repo.get("language") or UNKNOWN_LANGUAGE,
                "stars": int(repo.get("stargazers_count") or 0),
                "forks": int(repo.get("forks_count") or 0),
                "open_issues": int(repo.get("open_issues_count") or 0),
                "fork": bool(repo.get("fork")),
                "archived": bool(repo.get("archived")),
                "created_at": pd.to_datetime(repo.get("created_at"), utc=True),
                "updated_at": pd.to_datetime(repo.get("updated_at"), utc=True),
            }
        )
    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    df["popularity"] = df["stars"] + df["forks"]
    return df


def summary_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """Headline numbers for the top of the dashboard."""
    if df.empty:
        return {
            "repo_count": 0,
            "total_stars": 0,
            "total_forks": 0,
            "language_count": 0,
            "most_starred": None,
        }
    top = df.loc[df["stars"].idxmax()]
    return {
        "repo_count": int(len(df)),
        "total_stars": int(df["stars"].sum()),
        "total_forks": int(df["forks"].sum()),
        "language_count": int(df.loc[df["language"] != UNKNOWN_LANGUAGE, "language"].nunique()),
        "most_starred": {"name": top["name"], "stars": int(top["stars"]), "url": top["url"]},
    }


def language_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Repository count per primary language, with percentage share, largest first."""
    if df.empty:
        return pd.DataFrame(columns=["language", "repos", "percent"])
    counts = df["language"].value_counts().rename_axis("language").reset_index(name="repos")
    counts["percent"] = (counts["repos"] / counts["repos"].sum() * 100).round(1)
    return counts


def top_repositories(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Repositories ranked by popularity (stars + forks), for comparison charts."""
    return df.sort_values(["popularity", "stars"], ascending=False).head(top_n)


def filter_repositories(
    df: pd.DataFrame,
    search: str = "",
    languages: list[str] | None = None,
    include_forks: bool = True,
    include_archived: bool = True,
) -> pd.DataFrame:
    """Apply the sidebar filters. Search matches name or description, case-insensitively."""
    result = df
    if search and search.strip():
        term = search.strip().lower()
        mask = result["name"].str.lower().str.contains(term, regex=False) | result[
            "description"
        ].str.lower().str.contains(term, regex=False)
        result = result[mask]
    if languages:
        result = result[result["language"].isin(languages)]
    if not include_forks:
        result = result[~result["fork"]]
    if not include_archived:
        result = result[~result["archived"]]
    return result


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise the export columns to UTF-8 CSV bytes."""
    export = df.reindex(columns=EXPORT_COLUMNS).copy()
    for col in ("created_at", "updated_at"):
        export[col] = export[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return export.to_csv(index=False).encode("utf-8")
