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
