import asyncio

from semanticscholar_mcp_server import server


def test_search_semantic_scholar_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-1", "title": "A Paper"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "search_papers", lambda client, query, limit: expected)

    result = asyncio.run(server.search_semantic_scholar("transformers", 3))

    assert result == expected


def test_get_semantic_scholar_paper_details_returns_error(monkeypatch):
    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_paper_details", lambda client, paper_id: (_ for _ in ()).throw(ValueError("boom")))

    result = asyncio.run(server.get_semantic_scholar_paper_details("paper-123"))

    assert result == {"error": "An error occurred while fetching paper details: boom"}


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


def test_get_semantic_scholar_papers_batch_returns_helper_results(monkeypatch):
    expected = [{"paperId": "paper-2", "title": "Batch"}]

    monkeypatch.setattr(server, "client", object())
    monkeypatch.setattr(server, "get_papers_batch", lambda client, paper_ids: expected)

    result = asyncio.run(server.get_semantic_scholar_papers_batch(["paper-1", "paper-2"]))

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
