import pytest
import requests

from github_client import PER_PAGE, GitHubAPIError, GitHubClient, validate_username


class FakeResponse:
    def __init__(self, payload=None, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    @property
    def text(self):
        return str(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    """Returns queued responses in order and records each request's params."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_validate_username_accepts_valid_names():
    assert validate_username("  octocat ") == "octocat"
    assert validate_username("a-b-c") == "a-b-c"


@pytest.mark.parametrize("bad", ["", "-start", "end-", "double--dash", "has space", "x" * 40])
def test_validate_username_rejects_invalid_names(bad):
    with pytest.raises(GitHubAPIError):
        validate_username(bad)


def test_get_repos_follows_pagination():
    first_page = [{"name": f"r{i}"} for i in range(PER_PAGE)]
    second_page = [{"name": "last"}]
    session = FakeSession([FakeResponse(first_page), FakeResponse(second_page)])
    client = GitHubClient(session=session)

    repos = client.get_repos("octocat")

    assert len(repos) == PER_PAGE + 1
    assert [c["params"]["page"] for c in session.calls] == [1, 2]


def test_get_repos_single_short_page_makes_one_call():
    session = FakeSession([FakeResponse([{"name": "only"}])])
    client = GitHubClient(session=session)
    assert len(client.get_repos("octocat")) == 1
    assert len(session.calls) == 1


def test_404_becomes_friendly_error():
    client = GitHubClient(session=FakeSession([FakeResponse(status=404)]))
    with pytest.raises(GitHubAPIError, match="not found"):
        client.get_user("nobody")


def test_rate_limit_is_detected():
    response = FakeResponse(status=403, headers={"X-RateLimit-Remaining": "0"})
    client = GitHubClient(session=FakeSession([response]))
    with pytest.raises(GitHubAPIError, match="rate limit"):
        client.get_user("octocat")


def test_network_error_is_wrapped():
    client = GitHubClient(session=FakeSession([requests.ConnectionError("boom")]))
    with pytest.raises(GitHubAPIError, match="Network error"):
        client.get_user("octocat")


def test_token_sets_authorization_header():
    client = GitHubClient(token="abc123", session=FakeSession([]))
    assert client.session.headers["Authorization"] == "Bearer abc123"


def test_invalid_username_never_hits_network():
    session = FakeSession([])
    client = GitHubClient(session=session)
    with pytest.raises(GitHubAPIError):
        client.get_repos("bad name")
    assert session.calls == []
