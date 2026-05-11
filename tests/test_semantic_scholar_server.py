import asyncio

from semanticscholar_mcp_server import server


def test_search_semantic_scholar_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-1", "title": "A Paper"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "search_papers", lambda client, query, limit: expected)

    result = asyncio.run(server.search_semantic_scholar("transformers", 3))

    assert result == expected


def test_search_semantic_scholar_papers_advanced_returns_helper_results(monkeypatch):
    expected = {
        "total": 12,
        "offset": 0,
        "next": 5,
        "limit": 5,
        "returned": 5,
        "hasMore": True,
        "items": [{"paperId": "paper-1", "title": "Advanced"}],
    }

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "search_papers_advanced", lambda client, query, **kwargs: expected)

    result = asyncio.run(server.search_semantic_scholar_papers_advanced("transformers", limit=5))

    assert result == expected


def test_search_semantic_scholar_papers_bulk_returns_helper_results(monkeypatch):
    expected = {
        "total": 200,
        "nextToken": "token-2",
        "limit": 100,
        "returned": 100,
        "hasMore": True,
        "sort": "paperId",
        "items": [{"paperId": "paper-1", "title": "Bulk"}],
    }

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "search_papers_bulk", lambda client, query, **kwargs: expected)

    result = asyncio.run(server.search_semantic_scholar_papers_bulk("transformers", limit=100, sort="paperId"))

    assert result == expected


def test_get_semantic_scholar_paper_details_returns_error(monkeypatch):
    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_paper_details", lambda client, paper_id: (_ for _ in ()).throw(ValueError("boom")))

    result = asyncio.run(server.get_semantic_scholar_paper_details("paper-123"))

    assert result == {"error": "An error occurred while fetching paper details: boom"}


def test_match_semantic_scholar_paper_title_returns_helper_results(monkeypatch):
    expected = {"paperId": "paper-1", "title": "Matched", "matchScore": 0.99}

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_paper_title_match", lambda client, query, **kwargs: expected)

    result = asyncio.run(server.match_semantic_scholar_paper_title("matched title"))

    assert result == expected


def test_get_semantic_scholar_paper_autocomplete_returns_helper_results(monkeypatch):
    expected = [{"id": "paper-1", "title": "Matched", "authorsYear": "Doe et al., 2024"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_paper_autocomplete", lambda client, query, limit=10: expected)

    result = asyncio.run(server.get_semantic_scholar_paper_autocomplete("mat", 1))

    assert result == expected


def test_get_semantic_scholar_recommendations_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-2", "title": "Recommended"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(
        server,
        "get_recommended_papers",
        lambda client, paper_id, limit, pool_from: expected,
    )

    result = asyncio.run(server.get_semantic_scholar_recommendations("paper-1", 2, "recent"))

    assert result == expected


def test_get_semantic_scholar_recommendations_multi_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-2", "title": "Recommended"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(
        server,
        "get_multi_recommended_papers",
        lambda client, positive_paper_ids, **kwargs: expected,
    )

    result = asyncio.run(server.get_semantic_scholar_recommendations_multi(["paper-1"], ["paper-x"], 5))

    assert result == expected


def test_get_semantic_scholar_citations_returns_helper_results(monkeypatch):
    expected = {
        "total": 838,
        "offset": 0,
        "limit": 100,
        "returned": 1,
        "hasMore": True,
        "items": [{"paperId": "paper-1", "title": "Citation"}],
    }

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_citations_page", lambda client, paper_id, limit, offset: expected)

    result = asyncio.run(server.get_semantic_scholar_citations("paper-1", 100, 0))

    assert result == expected


def test_get_semantic_scholar_references_returns_helper_results(monkeypatch):
    expected = {
        "total": 12,
        "offset": 10,
        "limit": 10,
        "returned": 2,
        "hasMore": False,
        "items": [{"paperId": "paper-2", "title": "Reference"}],
    }

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_references_page", lambda client, paper_id, limit, offset: expected)

    result = asyncio.run(server.get_semantic_scholar_references("paper-1", 10, 10))

    assert result == expected


def test_get_semantic_scholar_authors_batch_returns_helper_results(monkeypatch):
    expected = [{"authorId": "1741101", "name": "Oren Etzioni"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_authors_batch", lambda client, author_ids, fields=None: expected)

    result = asyncio.run(server.get_semantic_scholar_authors_batch(["1741101"]))

    assert result == expected


def test_get_semantic_scholar_papers_batch_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-2", "title": "Batch"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_papers_batch", lambda client, paper_ids: expected)

    result = asyncio.run(server.get_semantic_scholar_papers_batch(["paper-1", "paper-2"]))

    assert result == expected


def test_get_semantic_scholar_bibtex_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-1", "title": "Paper", "bibtex": "@article{paper}"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_bibtex_exports", lambda client, paper_ids: expected)

    result = asyncio.run(server.get_semantic_scholar_bibtex(["paper-1"]))

    assert result == expected


def test_search_semantic_scholar_snippets_returns_helper_results(monkeypatch):
    expected = {"limit": 1, "returned": 1, "items": [{"score": 0.9}]}

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "search_snippets", lambda client, query, **kwargs: expected)

    result = asyncio.run(server.search_semantic_scholar_snippets("query", limit=1))

    assert result == expected


def test_get_semantic_scholar_status_returns_helper_results(monkeypatch):
    expected = {
        "version": "0.2.0",
        "apiKeyConfigured": False,
        "usingApiKey": False,
        "apiReachable": True,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "requestConfig": {
            "minSecondsBetweenRequests": 1.0,
            "timeoutSeconds": 30.0,
            "retry": {"attempts": 6, "minWaitSeconds": 1.0, "maxWaitSeconds": 30.0},
        },
    }

    monkeypatch.setattr(server, "get_server_status", lambda client: expected)

    result = asyncio.run(server.get_semantic_scholar_status())

    assert result == expected


def test_get_semantic_scholar_citations_and_references_returns_helper_results(monkeypatch):
    expected = {
        "citations": {"total": 10, "offset": 0, "limit": 2, "returned": 2, "hasMore": True, "items": []},
        "references": {"total": 4, "offset": 0, "limit": 2, "returned": 2, "hasMore": True, "items": []},
    }

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(
        server,
        "get_citations_and_references_page_pair",
        lambda client, paper_id, **kwargs: expected,
    )

    result = asyncio.run(server.get_semantic_scholar_citations_and_references("paper-1", 2, 0, 2, 0))

    assert result == expected
