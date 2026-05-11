import asyncio
import logging
import os
from typing import Literal, cast

from mcp.server.fastmcp import FastMCP

from semanticscholar_mcp_server.models import (
    AuthorDetailResult,
    AuthorListResult,
    AutocompleteListResult,
    BibtexListResult,
    BulkPaperSearchResult,
    FlexiblePaperDetailResult,
    FlexiblePaperListResult,
    HealthResult,
    PaperDetailResult,
    PaperListResult,
    PaperSearchResult,
    RelatedPageResult,
    RelatedResult,
    SnippetResult,
    ToolError,
)
from semanticscholar_mcp_server.search import (
    format_author,
    format_paper,
    get_author_details,
    get_author_papers,
    get_authors_batch,
    get_bibtex_exports,
    get_citations_and_references_page_pair,
    get_citations_page,
    get_multi_recommended_papers,
    get_paper_autocomplete,
    get_paper_details,
    get_paper_title_match,
    get_papers_batch,
    get_recommended_papers,
    get_references_page,
    get_server_status,
    initialize_client,
    search_authors,
    search_papers,
    search_papers_advanced,
    search_papers_bulk,
    search_snippets,
)


def configure_logging() -> None:
    level_name = os.getenv("SEMANTIC_SCHOLAR_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def tool_error(prefix: str, exc: Exception) -> ToolError:
    return {"error": f"{prefix}: {exc}"}


configure_logging()

mcp = FastMCP("semanticscholar")
client = initialize_client()


@mcp.tool()
async def search_semantic_scholar(query: str, num_results: int = 10) -> PaperListResult:
    """Search Semantic Scholar papers by keyword, phrase, or topic.

    Args:
        query: Plain-text search query to run against Semantic Scholar papers.
        num_results: Maximum number of papers to return.

    Returns:
        A list of matching papers with ids, titles, authors, venue, year, and citation metadata.
    """
    logging.info("Searching for papers with query: %s, num_results: %s", query, num_results)
    try:
        return await asyncio.to_thread(search_papers, client, query, num_results)
    except Exception as exc:
        return [tool_error("An error occurred while searching", exc)]


@mcp.tool()
async def search_semantic_scholar_papers_advanced(
    query: str,
    limit: int = 10,
    offset: int = 0,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: list[str] | None = None,
    publication_types: list[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: list[str] | None = None,
) -> PaperSearchResult:
    """Run advanced paper search with filters and pagination metadata."""
    logging.info("Running advanced paper search for query: %s", query)
    try:
        return await asyncio.to_thread(
            search_papers_advanced,
            client,
            query,
            limit=limit,
            offset=offset,
            year=year,
            start_year=start_year,
            end_year=end_year,
            fields_of_study=fields_of_study,
            publication_types=publication_types,
            open_access_only=open_access_only,
            min_citation_count=min_citation_count,
            fields=fields,
        )
    except Exception as exc:
        return tool_error("An error occurred while running advanced paper search", exc)


@mcp.tool()
async def search_semantic_scholar_papers_bulk(
    query: str,
    limit: int = 100,
    token: str | None = None,
    sort: str | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: list[str] | None = None,
    publication_types: list[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: list[str] | None = None,
) -> BulkPaperSearchResult:
    """Run bulk paper search with token-based pagination."""
    logging.info("Running bulk paper search for query: %s", query)
    try:
        return await asyncio.to_thread(
            search_papers_bulk,
            client,
            query,
            limit=limit,
            token=token,
            sort=sort,
            year=year,
            start_year=start_year,
            end_year=end_year,
            fields_of_study=fields_of_study,
            publication_types=publication_types,
            open_access_only=open_access_only,
            min_citation_count=min_citation_count,
            fields=fields,
        )
    except Exception as exc:
        return tool_error("An error occurred while running bulk paper search", exc)


@mcp.tool()
async def get_semantic_scholar_paper_details(paper_id: str) -> PaperDetailResult:
    """Fetch detailed metadata for a single Semantic Scholar paper."""
    logging.info("Fetching paper details for paper ID: %s", paper_id)
    try:
        paper = await asyncio.to_thread(get_paper_details, client, paper_id)
        return format_paper(paper)
    except Exception as exc:
        return tool_error("An error occurred while fetching paper details", exc)


@mcp.tool()
async def match_semantic_scholar_paper_title(
    query: str,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: list[str] | None = None,
    publication_types: list[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: list[str] | None = None,
) -> FlexiblePaperDetailResult:
    """Find the single paper whose title best matches a query."""
    logging.info("Finding paper title match for query: %s", query)
    try:
        return await asyncio.to_thread(
            get_paper_title_match,
            client,
            query,
            year=year,
            start_year=start_year,
            end_year=end_year,
            fields_of_study=fields_of_study,
            publication_types=publication_types,
            open_access_only=open_access_only,
            min_citation_count=min_citation_count,
            fields=fields,
        )
    except Exception as exc:
        return tool_error("An error occurred while matching paper title", exc)


@mcp.tool()
async def get_semantic_scholar_paper_autocomplete(query: str, limit: int = 10) -> AutocompleteListResult:
    """Return autocomplete suggestions for a partial paper query."""
    logging.info("Getting paper autocomplete for query: %s", query)
    try:
        return await asyncio.to_thread(get_paper_autocomplete, client, query, limit=limit)
    except Exception as exc:
        return [tool_error("An error occurred while fetching autocomplete suggestions", exc)]


@mcp.tool()
async def get_semantic_scholar_author_details(author_id: str) -> AuthorDetailResult:
    """Fetch detailed metadata for a single Semantic Scholar author."""
    logging.info("Fetching author details for author ID: %s", author_id)
    try:
        author = await asyncio.to_thread(get_author_details, client, author_id)
        return format_author(author)
    except Exception as exc:
        return tool_error("An error occurred while fetching author details", exc)


@mcp.tool()
async def get_semantic_scholar_authors_batch(
    author_ids: list[str], fields: list[str] | None = None
) -> AuthorListResult:
    """Fetch detailed metadata for multiple Semantic Scholar authors in one request."""
    logging.info("Fetching batch author details for %s author ids", len(author_ids))
    try:
        return await asyncio.to_thread(get_authors_batch, client, author_ids, fields=fields)
    except Exception as exc:
        return [tool_error("An error occurred while fetching authors in batch", exc)]


@mcp.tool()
async def search_semantic_scholar_authors(query: str, num_results: int = 10) -> AuthorListResult:
    """Search Semantic Scholar authors by name."""
    logging.info("Searching for authors with query: %s, num_results: %s", query, num_results)
    try:
        return await asyncio.to_thread(search_authors, client, query, num_results)
    except Exception as exc:
        return [tool_error("An error occurred while searching authors", exc)]


@mcp.tool()
async def get_semantic_scholar_author_papers(author_id: str, num_results: int = 10) -> PaperListResult:
    """List papers written by a specific Semantic Scholar author."""
    logging.info("Fetching papers for author ID: %s, num_results: %s", author_id, num_results)
    try:
        return await asyncio.to_thread(get_author_papers, client, author_id, num_results)
    except Exception as exc:
        return [tool_error("An error occurred while fetching author papers", exc)]


@mcp.tool()
async def get_semantic_scholar_citations_and_references(
    paper_id: str,
    citations_limit: int = 100,
    citations_offset: int = 0,
    references_limit: int = 100,
    references_offset: int = 0,
) -> RelatedResult:
    """Get bounded pages of citing papers and referenced papers for a seed paper."""
    logging.info("Fetching citations and references for paper ID: %s", paper_id)
    try:
        return await asyncio.to_thread(
            get_citations_and_references_page_pair,
            client,
            paper_id,
            citations_limit=citations_limit,
            citations_offset=citations_offset,
            references_limit=references_limit,
            references_offset=references_offset,
        )
    except Exception as exc:
        return tool_error("An error occurred while fetching citations and references", exc)


@mcp.tool()
async def get_semantic_scholar_citations(paper_id: str, limit: int = 100, offset: int = 0) -> RelatedPageResult:
    """Get a paginated page of citing papers with rich metadata."""
    logging.info("Fetching citations page for paper ID: %s, limit: %s, offset: %s", paper_id, limit, offset)
    try:
        return await asyncio.to_thread(get_citations_page, client, paper_id, limit, offset)
    except Exception as exc:
        return tool_error("An error occurred while fetching citations", exc)


@mcp.tool()
async def get_semantic_scholar_references(paper_id: str, limit: int = 100, offset: int = 0) -> RelatedPageResult:
    """Get a paginated page of referenced papers with rich metadata."""
    logging.info("Fetching references page for paper ID: %s, limit: %s, offset: %s", paper_id, limit, offset)
    try:
        return await asyncio.to_thread(get_references_page, client, paper_id, limit, offset)
    except Exception as exc:
        return tool_error("An error occurred while fetching references", exc)


@mcp.tool()
async def get_semantic_scholar_recommendations(
    paper_id: str, num_results: int = 10, pool_from: str = "recent"
) -> PaperListResult:
    """Recommend papers related to a seed paper."""
    logging.info(
        "Fetching recommendations for paper ID: %s, num_results: %s, pool_from: %s",
        paper_id,
        num_results,
        pool_from,
    )
    try:
        if pool_from not in {"recent", "all-cs"}:
            return [tool_error("Invalid recommendation pool", ValueError("pool_from must be 'recent' or 'all-cs'"))]
        return await asyncio.to_thread(
            get_recommended_papers, client, paper_id, num_results, cast(Literal["recent", "all-cs"], pool_from)
        )
    except Exception as exc:
        return [tool_error("An error occurred while fetching recommendations", exc)]


@mcp.tool()
async def get_semantic_scholar_recommendations_multi(
    positive_paper_ids: list[str],
    negative_paper_ids: list[str] | None = None,
    num_results: int = 25,
    fields: list[str] | None = None,
) -> FlexiblePaperListResult:
    """Recommend papers from multiple positive and negative seed papers."""
    logging.info(
        "Fetching multi-paper recommendations for %s positive and %s negative seeds",
        len(positive_paper_ids),
        len(negative_paper_ids or []),
    )
    try:
        return await asyncio.to_thread(
            get_multi_recommended_papers,
            client,
            positive_paper_ids,
            negative_paper_ids=negative_paper_ids,
            limit=num_results,
            fields=fields,
        )
    except Exception as exc:
        return [tool_error("An error occurred while fetching multi-paper recommendations", exc)]


@mcp.tool()
async def get_semantic_scholar_papers_batch(paper_ids: list[str]) -> PaperListResult:
    """Fetch detailed metadata for multiple Semantic Scholar papers in one request."""
    logging.info("Fetching batch paper details for %s paper ids", len(paper_ids))
    try:
        return await asyncio.to_thread(get_papers_batch, client, paper_ids)
    except Exception as exc:
        return [tool_error("An error occurred while fetching papers in batch", exc)]


@mcp.tool()
async def get_semantic_scholar_bibtex(paper_ids: list[str]) -> BibtexListResult:
    """Export BibTeX entries for one or more Semantic Scholar papers."""
    logging.info("Exporting BibTeX for %s paper ids", len(paper_ids))
    try:
        return await asyncio.to_thread(get_bibtex_exports, client, paper_ids)
    except Exception as exc:
        return [tool_error("An error occurred while exporting BibTeX", exc)]


@mcp.tool()
async def search_semantic_scholar_snippets(
    query: str,
    paper_ids: list[str] | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: list[str] | None = None,
    min_citation_count: int | None = None,
    limit: int = 10,
    fields: list[str] | None = None,
) -> SnippetResult:
    """Search Semantic Scholar text snippets."""
    logging.info("Searching snippets for query: %s", query)
    try:
        return await asyncio.to_thread(
            search_snippets,
            client,
            query,
            paper_ids=paper_ids,
            year=year,
            start_year=start_year,
            end_year=end_year,
            fields_of_study=fields_of_study,
            min_citation_count=min_citation_count,
            limit=limit,
            fields=fields,
        )
    except Exception as exc:
        return tool_error("An error occurred while searching snippets", exc)


@mcp.tool()
async def get_semantic_scholar_status() -> HealthResult:
    """Report server and API health information."""
    logging.info("Fetching Semantic Scholar MCP status")
    try:
        return await asyncio.to_thread(get_server_status, client)
    except Exception as exc:
        return tool_error("An error occurred while fetching server status", exc)


def main() -> None:
    logging.info("Starting Semantic Scholar MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
