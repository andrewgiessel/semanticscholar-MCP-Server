import asyncio
import logging
import os
from typing import Literal, cast

from mcp.server.fastmcp import FastMCP

from semanticscholar_mcp_server.models import (
    AuthorDetailResult,
    AuthorListResult,
    PaperDetailResult,
    PaperListResult,
    RelatedPageResult,
    RelatedResult,
    ToolError,
)
from semanticscholar_mcp_server.search import (
    get_citations_and_references_page_pair,
    get_citations_page,
    format_author,
    format_paper,
    get_author_details,
    get_author_papers,
    get_paper_details,
    get_papers_batch,
    get_recommended_papers,
    get_references_page,
    initialize_client,
    search_authors,
    search_papers,
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
async def get_semantic_scholar_paper_details(paper_id: str) -> PaperDetailResult:
    """Fetch detailed metadata for a single Semantic Scholar paper.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.

    Returns:
        A paper record with core metadata such as title, abstract, authors, venue, year, and citation count.
    """
    logging.info("Fetching paper details for paper ID: %s", paper_id)
    try:
        paper = await asyncio.to_thread(get_paper_details, client, paper_id)
        return format_paper(paper)
    except Exception as exc:
        return tool_error("An error occurred while fetching paper details", exc)


@mcp.tool()
async def get_semantic_scholar_author_details(author_id: str) -> AuthorDetailResult:
    """Fetch detailed metadata for a single Semantic Scholar author.

    Args:
        author_id: Semantic Scholar author id.

    Returns:
        An author record with name, affiliations, profile url, paper count, citation count, and h-index.
    """
    logging.info("Fetching author details for author ID: %s", author_id)
    try:
        author = await asyncio.to_thread(get_author_details, client, author_id)
        return format_author(author)
    except Exception as exc:
        return tool_error("An error occurred while fetching author details", exc)


@mcp.tool()
async def search_semantic_scholar_authors(query: str, num_results: int = 10) -> AuthorListResult:
    """Search Semantic Scholar authors by name.

    Args:
        query: Plain-text author name or partial name to search for.
        num_results: Maximum number of authors to return.

    Returns:
        A list of matching authors with profile metadata such as affiliations, paper count, and h-index.
    """
    logging.info("Searching for authors with query: %s, num_results: %s", query, num_results)
    try:
        return await asyncio.to_thread(search_authors, client, query, num_results)
    except Exception as exc:
        return [tool_error("An error occurred while searching authors", exc)]


@mcp.tool()
async def get_semantic_scholar_author_papers(author_id: str, num_results: int = 10) -> PaperListResult:
    """List papers written by a specific Semantic Scholar author.

    Args:
        author_id: Semantic Scholar author id.
        num_results: Maximum number of papers to return for the author.

    Returns:
        A list of the author's papers with ids, titles, authors, venue, year, and citation metadata.
    """
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
    """Get bounded pages of citing papers and referenced papers for a seed paper.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.
        citations_limit: Maximum number of citations to return in this page.
        citations_offset: Citation offset for pagination.
        references_limit: Maximum number of references to return in this page.
        references_offset: Reference offset for pagination.

    Returns:
        An object with paginated `citations` and `references` sections, each including richer related-paper metadata.
    """
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
async def get_semantic_scholar_citations(
    paper_id: str, limit: int = 100, offset: int = 0
) -> RelatedPageResult:
    """Get a paginated page of citing papers with rich metadata.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.
        limit: Maximum number of citing papers to return in this page.
        offset: Starting offset for pagination.

    Returns:
        A page of citations with total count, paging metadata, and richer paper fields.
    """
    logging.info("Fetching citations page for paper ID: %s, limit: %s, offset: %s", paper_id, limit, offset)
    try:
        return await asyncio.to_thread(get_citations_page, client, paper_id, limit, offset)
    except Exception as exc:
        return tool_error("An error occurred while fetching citations", exc)


@mcp.tool()
async def get_semantic_scholar_references(
    paper_id: str, limit: int = 100, offset: int = 0
) -> RelatedPageResult:
    """Get a paginated page of referenced papers with rich metadata.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.
        limit: Maximum number of referenced papers to return in this page.
        offset: Starting offset for pagination.

    Returns:
        A page of references with total count, paging metadata, and richer paper fields.
    """
    logging.info("Fetching references page for paper ID: %s, limit: %s, offset: %s", paper_id, limit, offset)
    try:
        return await asyncio.to_thread(get_references_page, client, paper_id, limit, offset)
    except Exception as exc:
        return tool_error("An error occurred while fetching references", exc)


@mcp.tool()
async def get_semantic_scholar_recommendations(
    paper_id: str, num_results: int = 10, pool_from: str = "recent"
) -> PaperListResult:
    """Recommend papers related to a seed paper.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.
        num_results: Maximum number of recommended papers to return.
        pool_from: Recommendation pool to use. Supported values are `recent` and `all-cs`.

    Returns:
        A list of recommended papers related to the seed paper, with the same summary fields used by paper search.
    """
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
async def get_semantic_scholar_papers_batch(paper_ids: list[str]) -> PaperListResult:
    """Fetch detailed metadata for multiple Semantic Scholar papers in one request.

    Args:
        paper_ids: List of Semantic Scholar paper ids or other supported paper identifiers.

    Returns:
        A list of paper records with the same summary fields used by paper search and recommendations.
    """
    logging.info("Fetching batch paper details for %s paper ids", len(paper_ids))
    try:
        return await asyncio.to_thread(get_papers_batch, client, paper_ids)
    except Exception as exc:
        return [tool_error("An error occurred while fetching papers in batch", exc)]


def main() -> None:
    logging.info("Starting Semantic Scholar MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
