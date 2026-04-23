import asyncio
import logging
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from semanticscholar_mcp_server.search import (
    format_author,
    format_paper,
    get_author_details,
    get_author_papers,
    get_citations_and_references,
    get_paper_details,
    get_recommended_papers,
    initialize_client,
    search_authors,
    search_papers,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

mcp = FastMCP("semanticscholar")
client = initialize_client()


@mcp.tool()
async def search_semantic_scholar(
    query: str, num_results: int = 10
) -> List[Dict[str, Any]]:
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
        return [{"error": f"An error occurred while searching: {exc}"}]


@mcp.tool()
async def get_semantic_scholar_paper_details(paper_id: str) -> Dict[str, Any]:
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
        return {"error": f"An error occurred while fetching paper details: {exc}"}


@mcp.tool()
async def get_semantic_scholar_author_details(author_id: str) -> Dict[str, Any]:
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
        return {"error": f"An error occurred while fetching author details: {exc}"}


@mcp.tool()
async def search_semantic_scholar_authors(
    query: str, num_results: int = 10
) -> List[Dict[str, Any]]:
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
        return [{"error": f"An error occurred while searching authors: {exc}"}]


@mcp.tool()
async def get_semantic_scholar_author_papers(
    author_id: str, num_results: int = 10
) -> List[Dict[str, Any]]:
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
        return [{"error": f"An error occurred while fetching author papers: {exc}"}]


@mcp.tool()
async def get_semantic_scholar_citations_and_references(
    paper_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """Get both citing papers and referenced papers for a seed paper.

    Args:
        paper_id: Semantic Scholar paper id, DOI, ArXiv id, or another supported paper identifier.

    Returns:
        An object with `citations` and `references` lists, each containing related paper summaries.
    """
    logging.info("Fetching citations and references for paper ID: %s", paper_id)
    try:
        paper = await asyncio.to_thread(get_paper_details, client, paper_id)
        citations_refs = await asyncio.to_thread(get_citations_and_references, paper)
        return {
            "citations": [
                {
                    "paperId": citation.paperId,
                    "title": citation.title,
                    "year": citation.year,
                    "authors": [
                        {"name": author.name, "authorId": author.authorId}
                        for author in citation.authors
                    ],
                }
                for citation in citations_refs["citations"]
            ],
            "references": [
                {
                    "paperId": reference.paperId,
                    "title": reference.title,
                    "year": reference.year,
                    "authors": [
                        {"name": author.name, "authorId": author.authorId}
                        for author in reference.authors
                    ],
                }
                for reference in citations_refs["references"]
            ],
        }
    except Exception as exc:
        return {"error": f"An error occurred while fetching citations and references: {exc}"}


@mcp.tool()
async def get_semantic_scholar_recommendations(
    paper_id: str, num_results: int = 10, pool_from: str = "recent"
) -> List[Dict[str, Any]]:
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
        return await asyncio.to_thread(
            get_recommended_papers, client, paper_id, num_results, pool_from
        )
    except Exception as exc:
        return [{"error": f"An error occurred while fetching recommendations: {exc}"}]


def main() -> None:
    logging.info("Starting Semantic Scholar MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
