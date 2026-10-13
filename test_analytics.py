import pandas as pd
import pytest

from analytics import (
    EXPORT_COLUMNS,
    filter_repositories,
    language_distribution,
    repos_to_dataframe,
    summary_metrics,
    to_csv_bytes,
    top_repositories,
)


def make_repo(**overrides):
    base = {
        "name": "alpha",
        "html_url": "https://github.com/u/alpha",
        "description": "A useful tool",
        "language": "Python",
        "stargazers_count": 10,
        "forks_count": 2,
        "open_issues_count": 1,
        "fork": False,
        "archived": False,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2024-06-01T00:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def df():
    repos = [
        make_repo(name="alpha", stargazers_count=10, forks_count=2, language="Python"),
        make_repo(name="beta", description=None, language=None, stargazers_count=50, forks_count=5),
        make_repo(name="gamma-fork", fork=True, language="Go", stargazers_count=1, forks_count=0,
                  description="Forked from upstream"),
        make_repo(name="delta", language="Python", archived=True, stargazers_count=3, forks_count=1,
                  description="Old Rust-free script"),
    ]
    return repos_to_dataframe(repos)


def test_normalises_missing_fields(df):
    beta = df[df["name"] == "beta"].iloc[0]
    assert beta["language"] == "Unknown"
    assert beta["description"] == ""


def test_dates_are_parsed_as_utc(df):
    assert str(df["created_at"].dt.tz) == "UTC"
    assert df.loc[0, "created_at"].year == 2020


def test_popularity_is_stars_plus_forks(df):
    assert df.loc[df["name"] == "alpha", "popularity"].item() == 12


def test_summary_metrics(df):
    metrics = summary_metrics(df)
    assert metrics["repo_count"] == 4
    assert metrics["total_stars"] == 64
    assert metrics["total_forks"] == 8
    assert metrics["language_count"] == 2  # Python and Go; Unknown is excluded
    assert metrics["most_starred"]["name"] == "beta"


def test_summary_metrics_empty():
    empty = repos_to_dataframe([])
    metrics = summary_metrics(empty)
    assert metrics["repo_count"] == 0
    assert metrics["most_starred"] is None


def test_language_distribution_percentages(df):
    dist = language_distribution(df).set_index("language")
    assert dist.loc["Python", "repos"] == 2
    assert dist.loc["Python", "percent"] == 50.0
    assert dist["percent"].sum() == pytest.approx(100.0, abs=0.5)


def test_top_repositories_orders_by_popularity(df):
    top = top_repositories(df, top_n=2)
    assert list(top["name"]) == ["beta", "alpha"]


def test_search_matches_name_and_description_case_insensitively(df):
    assert set(filter_repositories(df, search="USEFUL")["name"]) == {"alpha"}
    assert set(filter_repositories(df, search="beta")["name"]) == {"beta"}


def test_search_ignores_blank_term(df):
    assert len(filter_repositories(df, search="   ")) == len(df)


def test_language_filter(df):
    assert set(filter_repositories(df, languages=["Go"])["name"]) == {"gamma-fork"}


def test_exclude_forks_and_archived(df):
    names = set(filter_repositories(df, include_forks=False, include_archived=False)["name"])
    assert names == {"alpha", "beta"}


def test_csv_has_expected_columns_and_iso_dates(df):
    csv_text = to_csv_bytes(df).decode("utf-8")
    header = csv_text.splitlines()[0].split(",")
    assert header == EXPORT_COLUMNS
    assert "2020-01-01T00:00:00Z" in csv_text


def test_csv_handles_filtered_empty_frame(df):
    empty = filter_repositories(df, search="no-such-repo")
    csv_text = to_csv_bytes(empty).decode("utf-8")
    assert csv_text.splitlines() == [",".join(EXPORT_COLUMNS)]
