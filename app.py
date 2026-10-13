"""Streamlit dashboard: run with `streamlit run app.py`."""

from __future__ import annotations

import os

import plotly.express as px
import streamlit as st

from analytics import (
    filter_repositories,
    language_distribution,
    repos_to_dataframe,
    summary_metrics,
    to_csv_bytes,
    top_repositories,
)
from github_client import GitHubAPIError, GitHubClient, validate_username


@st.cache_data(ttl=600, show_spinner=False)
def load_profile_and_repos(username: str, token: str | None):
    """Fetch and normalise data. Cached for 10 minutes to protect the API rate limit."""
    client = GitHubClient(token=token)
    profile = client.get_user(username)
    repos = client.get_repos(username)
    return profile, repos_to_dataframe(repos)


def render_header(profile: dict) -> None:
    left, right = st.columns([1, 4])
    with left:
        if profile.get("avatar_url"):
            st.image(profile["avatar_url"], width=120)
    with right:
        st.subheader(profile.get("name") or profile["login"])
        st.markdown(f"[@{profile['login']} on GitHub]({profile['html_url']})")
        if profile.get("bio"):
            st.write(profile["bio"])


def render_metrics(df) -> None:
    metrics = summary_metrics(df)
    cols = st.columns(4)
    cols[0].metric("Public repositories", metrics["repo_count"])
    cols[1].metric("Total stars", metrics["total_stars"])
    cols[2].metric("Total forks", metrics["total_forks"])
    cols[3].metric("Languages used", metrics["language_count"])
    if metrics["most_starred"]:
        top = metrics["most_starred"]
        st.caption(f"Most starred: [{top['name']}]({top['url']}) with {top['stars']} stars")


def render_charts(df) -> None:
    lang_col, pop_col = st.columns(2)
    with lang_col:
        st.markdown("#### Language distribution")
        dist = language_distribution(df)
        if dist.empty:
            st.info("No repositories to chart.")
        else:
            fig = px.pie(dist, names="language", values="repos", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    with pop_col:
        st.markdown("#### Repository popularity (stars + forks)")
        top = top_repositories(df, top_n=15)
        if top.empty:
            st.info("No repositories to chart.")
        else:
            fig = px.bar(
                top.sort_values("popularity"),
                x="popularity",
                y="name",
                orientation="h",
                hover_data={"stars": True, "forks": True, "language": True},
            )
            fig.update_layout(yaxis_title=None, xaxis_title="Stars + forks")
            st.plotly_chart(fig, use_container_width=True)


def render_repo_table(df) -> None:
    st.dataframe(
        df[["name", "url", "description", "language", "stars", "forks", "created_at", "updated_at"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Repository", display_text="Open"),
            "description": st.column_config.TextColumn("Description", width="large"),
            "created_at": st.column_config.DatetimeColumn("Created", format="YYYY-MM-DD"),
            "updated_at": st.column_config.DatetimeColumn("Last updated", format="YYYY-MM-DD"),
        },
    )


def render_repo_details(df) -> None:
    if df.empty:
        return
    choice = st.selectbox("Repository details", df["name"].tolist())
    repo = df[df["name"] == choice].iloc[0]
    st.markdown(f"**[{repo['name']}]({repo['url']})**")
    st.write(repo["description"] or "_No description provided._")
    details = st.columns(4)
    details[0].metric("Stars", int(repo["stars"]))
    details[1].metric("Forks", int(repo["forks"]))
    details[2].metric("Open issues", int(repo["open_issues"]))
    details[3].metric("Language", repo["language"])
    st.caption(
        f"Created {repo['created_at']:%Y-%m-%d} · Last updated {repo['updated_at']:%Y-%m-%d}"
        + (" · Fork" if repo["fork"] else "")
        + (" · Archived" if repo["archived"] else "")
    )


def main() -> None:
    st.set_page_config(page_title="GitHub Repository Analytics", layout="wide")
    st.title("GitHub Repository Analytics")

    with st.sidebar:
        st.header("Source")
        username_input = st.text_input("GitHub username", value="torvalds")
        token = st.text_input(
            "Personal access token (optional)",
            type="password",
            value=os.getenv("GITHUB_TOKEN", ""),
            help="Raises the API limit from 60 to 5,000 requests per hour. Never stored or logged.",
        )
        analyze = st.button("Analyze", type="primary", use_container_width=True)

    if analyze:
        try:
            username = validate_username(username_input)
            with st.spinner(f"Fetching data for {username}..."):
                st.session_state["data"] = load_profile_and_repos(username, token or None)
        except GitHubAPIError as exc:
            st.session_state.pop("data", None)
            st.error(str(exc))

    if "data" not in st.session_state:
        st.info("Enter a GitHub username in the sidebar and press Analyze.")
        return

    profile, df = st.session_state["data"]
    render_header(profile)

    if df.empty:
        st.warning("This user has no public repositories.")
        return

    st.divider()
    render_metrics(df)
    st.divider()

    st.sidebar.header("Filters")
    search = st.sidebar.text_input("Search name or description")
    languages = st.sidebar.multiselect("Languages", sorted(df["language"].unique()))
    include_forks = st.sidebar.checkbox("Include forks", value=True)
    include_archived = st.sidebar.checkbox("Include archived", value=True)

    filtered = filter_repositories(
        df,
        search=search,
        languages=languages,
        include_forks=include_forks,
        include_archived=include_archived,
    )
    st.caption(f"Showing {len(filtered)} of {len(df)} repositories")

    render_charts(filtered)
    st.divider()
    render_repo_details(filtered)
    st.divider()
    render_repo_table(filtered)

    st.download_button(
        "Download CSV report",
        data=to_csv_bytes(filtered),
        file_name=f"{profile['login']}_repositories.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
