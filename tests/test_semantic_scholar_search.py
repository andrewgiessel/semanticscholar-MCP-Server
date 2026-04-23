from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Literal

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from semanticscholar_mcp_server import search as search_module


@dataclass
class AuthorStub:
    authorId: str | None
    name: str | None
    url: str | None = None
    affiliations: list[str] | None = None
    paperCount: int | None = None
    citationCount: int | None = None
    hIndex: int | None = None


@dataclass
class PaperStub:
    paperId: str | None
    title: str | None
    abstract: str | None = None
    year: int | None = None
    publicationDate: str | None = None
    authors: list[AuthorStub] = field(default_factory=list)
    url: str | None = None
    venue: str | None = None
    publicationTypes: list[str] | None = None
    citationCount: int | None = None
    externalIds: dict[str, str] | None = None
    citations: list[PaperStub] = field(default_factory=list)
    references: list[PaperStub] = field(default_factory=list)


def test_initialize_client_uses_api_key_when_present(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key")

    client = search_module.initialize_client()

    assert client._api_key == "test-key"
    assert client._using_api_key is True


def test_initialize_client_uses_public_access_when_key_missing(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    client = search_module.initialize_client()

    assert client._api_key is None
    assert client._using_api_key is False


def test_is_rate_limited_only_matches_429_connection_errors():
    assert search_module._is_rate_limited(ConnectionRefusedError("HTTP status 429 Too Many Requests."))
    assert not search_module._is_rate_limited(ConnectionRefusedError("HTTP status 403 Forbidden."))
    assert not search_module._is_rate_limited(RuntimeError("HTTP status 429 Too Many Requests."))


def test_is_forbidden_only_matches_403_permission_errors():
    assert search_module._is_forbidden(PermissionError("HTTP status 403 Forbidden."))
    assert not search_module._is_forbidden(PermissionError("HTTP status 429 Too Many Requests."))
    assert not search_module._is_forbidden(RuntimeError("HTTP status 403 Forbidden."))


def test_request_throttle_waits_for_minimum_interval(monkeypatch):
    now = {"value": 100.0}
    sleeps = []

    def fake_monotonic():
        return now["value"]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now["value"] += seconds

    monkeypatch.setattr(search_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(search_module.time, "sleep", fake_sleep)

    throttle = search_module.RequestThrottle(1.0)
    throttle.wait_for_turn()
    throttle.wait_for_turn()

    assert sleeps == [1.0]


def test_search_papers_shapes_results():
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Attention Is All You Need",
        abstract="Transformers replace recurrence.",
        year=2017,
        publicationDate="2017-06-12",
        authors=[
            SimpleNamespace(name="Ashish Vaswani", authorId="author-1"),
            SimpleNamespace(name="Noam Shazeer", authorId="author-2"),
        ],
        url="https://example.com/paper-1",
        venue="NeurIPS",
        publicationTypes=["JournalArticle"],
        citationCount=12345,
        externalIds={"DOI": "10.5555/test-doi", "ArXiv": "1706.03762"},
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def search_paper(self, query, limit=10):
            self.calls.append((query, limit))
            return [paper]

    client = FakeClient()

    results = search_module.search_papers(client, "transformers", 5)

    assert client.calls == [("transformers", 5)]
    assert results == [
        {
            "paperId": "paper-1",
            "title": "Attention Is All You Need",
            "abstract": "Transformers replace recurrence.",
            "year": 2017,
            "publicationDate": "2017-06-12",
            "authors": [
                {"name": "Ashish Vaswani", "authorId": "author-1"},
                {"name": "Noam Shazeer", "authorId": "author-2"},
            ],
            "url": "https://example.com/paper-1",
            "venue": "NeurIPS",
            "publicationTypes": ["JournalArticle"],
            "citationCount": 12345,
            "externalIds": {"DOI": "10.5555/test-doi", "ArXiv": "1706.03762"},
            "doi": "10.5555/test-doi",
            "pmid": None,
            "arxivId": "1706.03762",
        }
    ]


def test_search_papers_uses_loaded_items_without_iterating():
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Loaded page result",
        abstract=None,
        year=2024,
        publicationDate=None,
        authors=[],
        url="https://example.com/paper-1",
        venue=None,
        publicationTypes=None,
        citationCount=1,
        externalIds=None,
    )

    class FakePaginatedResults:
        def __init__(self):
            self.items = [paper]

        def __iter__(self):
            raise AssertionError("search_papers should not iterate paginated results")

    class FakeClient:
        def search_paper(self, query, limit=10):
            return FakePaginatedResults()

    results = search_module.search_papers(FakeClient(), "transformers", 1)

    assert results[0]["title"] == "Loaded page result"


def test_search_authors_shapes_results():
    author = SimpleNamespace(
        authorId="author-1",
        name="Ashish Vaswani",
        url="https://example.com/author-1",
        affiliations=["Google Brain"],
        paperCount=42,
        citationCount=9999,
        hIndex=55,
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def search_author(self, query, limit=10):
            self.calls.append((query, limit))
            return [author]

    client = FakeClient()

    results = search_module.search_authors(client, "vaswani", 5)

    assert client.calls == [("vaswani", 5)]
    assert results == [
        {
            "authorId": "author-1",
            "name": "Ashish Vaswani",
            "url": "https://example.com/author-1",
            "affiliations": ["Google Brain"],
            "paperCount": 42,
            "citationCount": 9999,
            "hIndex": 55,
        }
    ]


def test_search_papers_retries_rate_limits(monkeypatch):
    attempts = {"count": 0}
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Recovered after retry",
        abstract=None,
        year=2024,
        publicationDate=None,
        authors=[],
        url="https://example.com/paper-1",
        venue=None,
        publicationTypes=None,
        citationCount=1,
        externalIds=None,
    )

    class FakeClient:
        def search_paper(self, query, limit=10):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ConnectionRefusedError("HTTP status 429 Too Many Requests.")
            return [paper]

    def fake_semantic_scholar(*, retry=True, api_key=None):
        return FakeClient()

    monkeypatch.setattr(
        search_module,
        "RATE_LIMIT_RETRYER",
        Retrying(
            retry=retry_if_exception(search_module._is_rate_limited),
            wait=wait_fixed(0),
            stop=stop_after_attempt(3),
            reraise=True,
        ),
    )
    monkeypatch.setattr(search_module, "SemanticScholar", fake_semantic_scholar)

    client = search_module.SemanticScholarClient(api_key=None)
    results = search_module.search_papers(client, "transformers", 1)

    assert attempts["count"] == 3
    assert results[0]["title"] == "Recovered after retry"


def test_search_papers_throttles_each_attempt(monkeypatch):
    attempts = {"count": 0}
    wait_calls = {"count": 0}
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Recovered after paced retry",
        abstract=None,
        year=2024,
        publicationDate=None,
        authors=[],
        url="https://example.com/paper-1",
        venue=None,
        publicationTypes=None,
        citationCount=1,
        externalIds=None,
    )

    class FakeClient:
        def search_paper(self, query, limit=10):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ConnectionRefusedError("HTTP status 429 Too Many Requests.")
            return [paper]

    class FakeThrottle:
        def wait_for_turn(self):
            wait_calls["count"] += 1

    def fake_semantic_scholar(*, retry=True, api_key=None):
        return FakeClient()

    monkeypatch.setattr(
        search_module,
        "RATE_LIMIT_RETRYER",
        Retrying(
            retry=retry_if_exception(search_module._is_rate_limited),
            wait=wait_fixed(0),
            stop=stop_after_attempt(3),
            reraise=True,
        ),
    )
    monkeypatch.setattr(search_module, "SemanticScholar", fake_semantic_scholar)

    client = search_module.SemanticScholarClient(api_key=None)
    client._throttle = FakeThrottle()
    results = search_module.search_papers(client, "transformers", 1)

    assert attempts["count"] == 3
    assert wait_calls["count"] == 3
    assert results[0]["title"] == "Recovered after paced retry"


def test_search_papers_disables_api_key_after_403(monkeypatch):
    authenticated_client = SimpleNamespace()
    anonymous_client = SimpleNamespace()
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Recovered without key",
        abstract=None,
        year=2024,
        publicationDate=None,
        authors=[],
        url="https://example.com/paper-1",
        venue=None,
        publicationTypes=None,
        citationCount=1,
        externalIds=None,
    )

    attempts = {"auth": 0, "anon": 0}

    def auth_search(query, limit=10):
        attempts["auth"] += 1
        raise PermissionError("HTTP status 403 Forbidden.")

    def anon_search(query, limit=10):
        attempts["anon"] += 1
        return [paper]

    authenticated_client.search_paper = auth_search
    anonymous_client.search_paper = anon_search

    clients = []

    def fake_semantic_scholar(*, retry=True, api_key=None):
        client = authenticated_client if api_key else anonymous_client
        clients.append((api_key, retry))
        return client

    monkeypatch.setattr(search_module, "SemanticScholar", fake_semantic_scholar)

    client = search_module.SemanticScholarClient(api_key="bad-key")
    results = search_module.search_papers(client, "transformers", 1)

    assert attempts == {"auth": 1, "anon": 1}
    assert clients == [("bad-key", False), (None, False)]
    assert client._using_api_key is False
    assert results[0]["title"] == "Recovered without key"


def test_get_author_papers_shapes_results():
    paper = SimpleNamespace(
        paperId="paper-1",
        title="Attention Is All You Need",
        abstract="Transformers replace recurrence.",
        year=2017,
        publicationDate="2017-06-12",
        authors=[SimpleNamespace(name="Ashish Vaswani", authorId="author-1")],
        url="https://example.com/paper-1",
        venue="NeurIPS",
        publicationTypes=["JournalArticle"],
        citationCount=12345,
        externalIds=None,
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_author_papers(self, author_id, limit=100):
            self.calls.append((author_id, limit))
            return [paper]

    client = FakeClient()

    results = search_module.get_author_papers(client, "author-1", 5)

    assert client.calls == [("author-1", 5)]
    assert results[0]["title"] == "Attention Is All You Need"


def test_get_recommended_papers_shapes_results():
    paper = PaperStub(
        paperId="paper-2",
        title="A Recommended Paper",
        year=2024,
        publicationDate="2024-01-01",
        url="https://example.com/paper-2",
        citationCount=7,
        externalIds={"PubMed": "12345"},
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_recommended_papers(
            self,
            paper_id: str,
            limit: int = 10,
            pool_from: Literal["recent", "all-cs"] = "recent",
        ) -> list[PaperStub]:
            self.calls.append((paper_id, limit, pool_from))
            return [paper]

    client = FakeClient()

    results = search_module.get_recommended_papers(client, "paper-1", 3, "all-cs")

    assert client.calls == [("paper-1", 3, "all-cs")]
    assert results[0]["title"] == "A Recommended Paper"


def test_get_paper_details_delegates_to_client():
    expected_paper = PaperStub(
        paperId="paper-123",
        title="A Paper",
        year=2024,
        publicationDate="2024-01-01",
        url="https://example.com/paper-123",
        citationCount=1,
    )

    class FakeClient:
        def get_paper(self, paper_id: str) -> PaperStub:
            assert paper_id == "paper-123"
            return expected_paper

    result = search_module.get_paper_details(FakeClient(), "paper-123")

    assert result is expected_paper


def test_get_author_details_delegates_to_client():
    expected_author = AuthorStub(
        authorId="author-123",
        name="An Author",
        url="https://example.com/author-123",
        affiliations=[],
        paperCount=1,
        citationCount=1,
        hIndex=1,
    )

    class FakeClient:
        def get_author(self, author_id: str) -> AuthorStub:
            assert author_id == "author-123"
            return expected_author

    result = search_module.get_author_details(FakeClient(), "author-123")

    assert result is expected_author


def test_get_citations_and_references_returns_existing_lists():
    citations = [
        PaperStub(
            paperId="citation-1",
            title="A citing paper",
            abstract="Citer abstract",
            year=2020,
            publicationDate="2020-05-01",
            authors=[AuthorStub(name="Citing Author", authorId="author-1")],
            url="https://example.com/citation-1",
            venue="TestConf",
            publicationTypes=["JournalArticle"],
            citationCount=20,
            externalIds={"DOI": "10.1000/citation"},
        )
    ]
    references = [
        PaperStub(
            paperId="reference-1",
            title="A referenced paper",
            abstract="Reference abstract",
            year=2019,
            publicationDate="2019-04-01",
            authors=[AuthorStub(name="Referenced Author", authorId="author-2")],
            url="https://example.com/reference-1",
            venue="RefConf",
            publicationTypes=["Conference"],
            citationCount=11,
            externalIds={"PubMed": "9988"},
        )
    ]
    paper = PaperStub(paperId="paper-1", title="Seed", citations=citations, references=references)

    result = search_module.get_citations_and_references(paper)

    assert result == {
        "citations": {
            "total": 1,
            "offset": 0,
            "limit": 1,
            "returned": 1,
            "hasMore": False,
            "items": [
                {
                    "paperId": "citation-1",
                    "title": "A citing paper",
                    "abstract": "Citer abstract",
                    "year": 2020,
                    "publicationDate": "2020-05-01",
                    "authors": [{"name": "Citing Author", "authorId": "author-1"}],
                    "url": "https://example.com/citation-1",
                    "venue": "TestConf",
                    "publicationTypes": ["JournalArticle"],
                    "citationCount": 20,
                    "externalIds": {"DOI": "10.1000/citation"},
                    "doi": "10.1000/citation",
                    "pmid": None,
                    "arxivId": None,
                    "contexts": None,
                    "intents": None,
                    "isInfluential": None,
                }
            ],
        },
        "references": {
            "total": 1,
            "offset": 0,
            "limit": 1,
            "returned": 1,
            "hasMore": False,
            "items": [
                {
                    "paperId": "reference-1",
                    "title": "A referenced paper",
                    "abstract": "Reference abstract",
                    "year": 2019,
                    "publicationDate": "2019-04-01",
                    "authors": [{"name": "Referenced Author", "authorId": "author-2"}],
                    "url": "https://example.com/reference-1",
                    "venue": "RefConf",
                    "publicationTypes": ["Conference"],
                    "citationCount": 11,
                    "externalIds": {"PubMed": "9988"},
                    "doi": None,
                    "pmid": "9988",
                    "arxivId": None,
                    "contexts": None,
                    "intents": None,
                    "isInfluential": None,
                }
            ],
        },
    }


def test_get_citations_page_formats_rich_paginated_response():
    class FakeClient:
        def get_paper_citations_page(self, paper_id, limit=100, offset=0):
            assert (paper_id, limit, offset) == ("paper-1", 2, 5)
            return {
                "total": 838,
                "data": [
                    {
                        "contexts": ["important context"],
                        "intents": ["Background"],
                        "isInfluential": True,
                        "citingPaper": {
                            "paperId": "citation-1",
                            "title": "A citing paper",
                            "abstract": "Citer abstract",
                            "year": 2020,
                            "publicationDate": "2020-05-01",
                            "authors": [{"name": "Citing Author", "authorId": "author-1"}],
                            "url": "https://example.com/citation-1",
                            "venue": "TestConf",
                            "publicationTypes": ["JournalArticle"],
                            "citationCount": 20,
                            "externalIds": {"DOI": "10.1000/citation"},
                        },
                    }
                ],
            }

    result = search_module.get_citations_page(FakeClient(), "paper-1", 2, 5)

    assert result == {
        "total": 838,
        "offset": 5,
        "limit": 2,
        "returned": 1,
        "hasMore": True,
        "items": [
            {
                "paperId": "citation-1",
                "title": "A citing paper",
                "abstract": "Citer abstract",
                "year": 2020,
                "publicationDate": "2020-05-01",
                "authors": [{"name": "Citing Author", "authorId": "author-1"}],
                "url": "https://example.com/citation-1",
                "venue": "TestConf",
                "publicationTypes": ["JournalArticle"],
                "citationCount": 20,
                "externalIds": {"DOI": "10.1000/citation"},
                "doi": "10.1000/citation",
                "pmid": None,
                "arxivId": None,
                "contexts": ["important context"],
                "intents": ["Background"],
                "isInfluential": True,
            }
        ],
    }


def test_get_references_page_formats_rich_paginated_response():
    class FakeClient:
        def get_paper_references_page(self, paper_id, limit=100, offset=0):
            assert (paper_id, limit, offset) == ("paper-1", 2, 0)
            return {
                "total": 12,
                "data": [
                    {
                        "contexts": None,
                        "intents": None,
                        "isInfluential": False,
                        "citedPaper": {
                            "paperId": "reference-1",
                            "title": "A referenced paper",
                            "abstract": "Reference abstract",
                            "year": 2019,
                            "publicationDate": "2019-04-01",
                            "authors": [{"name": "Referenced Author", "authorId": "author-2"}],
                            "url": "https://example.com/reference-1",
                            "venue": "RefConf",
                            "publicationTypes": ["Conference"],
                            "citationCount": 11,
                            "externalIds": {"PubMed": "9988"},
                        },
                    }
                ],
            }

    result = search_module.get_references_page(FakeClient(), "paper-1", 2, 0)

    assert result["hasMore"] is True
    assert result["items"][0]["pmid"] == "9988"


def test_get_citations_and_references_page_pair_combines_pages(monkeypatch):
    citations_page = {
        "total": 10,
        "offset": 0,
        "limit": 2,
        "returned": 2,
        "hasMore": True,
        "items": [{"paperId": "citation-1", "title": "Citation"}],
    }
    references_page = {
        "total": 4,
        "offset": 2,
        "limit": 2,
        "returned": 2,
        "hasMore": False,
        "items": [{"paperId": "reference-1", "title": "Reference"}],
    }

    monkeypatch.setattr(search_module, "get_citations_page", lambda client, paper_id, limit, offset: citations_page)
    monkeypatch.setattr(search_module, "get_references_page", lambda client, paper_id, limit, offset: references_page)

    class FakeClient:
        def get_paper_citations_page(self, paper_id, limit=100, offset=0):
            raise AssertionError("should not be called directly")

        def get_paper_references_page(self, paper_id, limit=100, offset=0):
            raise AssertionError("should not be called directly")

    result = search_module.get_citations_and_references_page_pair(
        FakeClient(),
        "paper-1",
        citations_limit=2,
        citations_offset=0,
        references_limit=2,
        references_offset=2,
    )

    assert result == {
        "citations": citations_page,
        "references": references_page,
    }


def test_get_papers_batch_shapes_results():
    paper = PaperStub(
        paperId="paper-2",
        title="Batch Paper",
        year=2024,
        publicationDate="2024-01-01",
        externalIds={"ArXiv": "1234.5678"},
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_papers(self, paper_ids):
            self.calls.append(paper_ids)
            return [paper]

    client = FakeClient()

    results = search_module.get_papers_batch(client, ["paper-2"])

    assert client.calls == [["paper-2"]]
    assert results[0]["arxivId"] == "1234.5678"


def test_get_citations_page_validates_arguments():
    class FakeClient:
        def get_paper_citations_page(self, paper_id, limit=100, offset=0):
            raise AssertionError("should not be called")

    try:
        search_module.get_citations_page(FakeClient(), "paper-1", 0, 0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("expected ValueError")
