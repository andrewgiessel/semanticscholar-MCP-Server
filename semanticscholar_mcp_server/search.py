import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Literal

import semanticscholar as sch
from dotenv import load_dotenv
from semanticscholar import Author, Paper, SemanticScholar
from tenacity import Retrying, before_sleep_log, retry_if_exception, stop_after_attempt, wait_exponential


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
logger = logging.getLogger(__name__)
MIN_SECONDS_BETWEEN_REQUESTS = 1.0


def _is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, ConnectionRefusedError) and "429" in str(exc)


def _is_forbidden(exc: BaseException) -> bool:
    return isinstance(exc, PermissionError) and "403" in str(exc)


RATE_LIMIT_RETRYER = Retrying(
    retry=retry_if_exception(_is_rate_limited),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _call_with_rate_limit_retry(func, *args, **kwargs):
    return RATE_LIMIT_RETRYER(func, *args, **kwargs)


class RequestThrottle:
    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_started_at = 0.0

    def wait_for_turn(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_started_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
            self._last_request_started_at = now


class SemanticScholarClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or None
        self._using_api_key = bool(self._api_key)
        self._throttle = RequestThrottle(MIN_SECONDS_BETWEEN_REQUESTS)
        self._client = self._build_client(api_key=self._api_key)

    def _build_client(self, api_key: str | None = None) -> SemanticScholar:
        return SemanticScholar(api_key=api_key, retry=False)

    def _disable_api_key(self) -> None:
        self._using_api_key = False
        self._client = self._build_client(api_key=None)

    def _call(self, method_name: str, *args, **kwargs):
        def call_once():
            self._throttle.wait_for_turn()
            method = getattr(self._client, method_name)
            return method(*args, **kwargs)

        try:
            return _call_with_rate_limit_retry(call_once)
        except Exception as exc:
            if self._using_api_key and _is_forbidden(exc):
                logger.warning(
                    "Semantic Scholar rejected the configured API key with 403; "
                    "disabling authenticated requests and falling back to public access."
                )
                self._disable_api_key()
                return _call_with_rate_limit_retry(call_once)
            raise

    def search_paper(self, query: str, limit: int = 10):
        return self._call("search_paper", query, limit=limit)

    def get_paper(self, paper_id: str):
        return self._call("get_paper", paper_id)

    def get_author(self, author_id: str):
        return self._call("get_author", author_id)

    def search_author(self, query: str, limit: int = 10):
        return self._call("search_author", query, limit=limit)

    def get_author_papers(self, author_id: str, limit: int = 100):
        return self._call("get_author_papers", author_id, limit=limit)

    def get_recommended_papers(
        self, paper_id: str, limit: int = 10, pool_from: Literal["recent", "all-cs"] = "recent"
    ):
        return self._call("get_recommended_papers", paper_id, limit=limit, pool_from=pool_from)


def initialize_client() -> SemanticScholarClient:
    """Initialize a client that can fall back to public access on 403."""
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
    return SemanticScholarClient(api_key=api_key)


def format_paper(paper: Paper) -> Dict[str, Any]:
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "authors": [
            {"name": author.name, "authorId": author.authorId}
            for author in paper.authors
        ],
        "url": paper.url,
        "venue": paper.venue,
        "publicationTypes": paper.publicationTypes,
        "citationCount": paper.citationCount,
    }


def format_author(author: Author) -> Dict[str, Any]:
    return {
        "authorId": author.authorId,
        "name": author.name,
        "url": author.url,
        "affiliations": author.affiliations,
        "paperCount": author.paperCount,
        "citationCount": author.citationCount,
        "hIndex": author.hIndex,
    }


def _loaded_items(results):
    """Return only the items already loaded by the client library.

    The semanticscholar PaginatedResults iterator eagerly fetches additional
    pages during iteration, which has proven unreliable for some endpoints.
    Using `.items` keeps us on the already-fetched page returned by the
    original request.
    """
    return getattr(results, "items", results)


def search_papers(
    client: SemanticScholarClient, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Search for papers using a query string."""
    results = client.search_paper(query, limit=limit)
    return [format_paper(paper) for paper in _loaded_items(results)]


def search_authors(
    client: SemanticScholarClient, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Search for authors by name."""
    results = client.search_author(query, limit=limit)
    return [format_author(author) for author in _loaded_items(results)]


def get_paper_details(client: SemanticScholarClient, paper_id: str) -> Paper:
    """Get details of a specific paper."""
    return client.get_paper(paper_id)


def get_author_details(client: SemanticScholarClient, author_id: str) -> Author:
    """Get details of a specific author."""
    return client.get_author(author_id)


def get_author_papers(
    client: SemanticScholarClient, author_id: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Get papers for a specific author."""
    results = client.get_author_papers(author_id, limit=limit)
    return [format_paper(paper) for paper in _loaded_items(results)]


def get_recommended_papers(
    client: SemanticScholarClient,
    paper_id: str,
    limit: int = 10,
    pool_from: Literal["recent", "all-cs"] = "recent",
) -> List[Dict[str, Any]]:
    """Get recommended papers for a seed paper."""
    results = client.get_recommended_papers(paper_id, limit=limit, pool_from=pool_from)
    return [format_paper(paper) for paper in results]


def get_citations_and_references(paper: Paper) -> Dict[str, List[Dict[str, Any]]]:
    """Get citations and references for a paper."""
    return {
        "citations": paper.citations,
        "references": paper.references,
    }


def main() -> None:
    try:
        client = initialize_client()

        search_results = search_papers(client, "machine learning")
        print(f"Search results: {search_results[:2]}")

        if search_results:
            paper_id = search_results[0]["paperId"]
            paper = get_paper_details(client, paper_id)
            print(f"Paper details: {paper}")

            citations_refs = get_citations_and_references(paper)
            print(f"Citations: {citations_refs['citations'][:2]}")
            print(f"References: {citations_refs['references'][:2]}")

        author_id = "1741101"
        author = get_author_details(client, author_id)
        print(f"Author details: {author}")

    except sch.SemanticScholarException as exc:
        print(f"An error occurred: {exc}")


if __name__ == "__main__":
    main()
