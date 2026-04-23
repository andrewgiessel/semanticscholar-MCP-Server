import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, TypeVar, cast

from dotenv import load_dotenv
from semanticscholar import SemanticScholar
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from semanticscholar_mcp_server.models import (
    AuthorSummary,
    CitationsAndReferences,
    PaperAuthor,
    PaperSummary,
    RelatedPaperSummary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")
ItemT = TypeVar("ItemT", covariant=True)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid %s value %r; using default %s", name, value, default)
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s value %r; using default %s", name, value, default)
        return default


MIN_SECONDS_BETWEEN_REQUESTS = _env_float("SEMANTIC_SCHOLAR_MIN_SECONDS_BETWEEN_REQUESTS", 1.0)
RETRY_ATTEMPTS = _env_int("SEMANTIC_SCHOLAR_RETRY_ATTEMPTS", 6)
RETRY_MIN_WAIT_SECONDS = _env_float("SEMANTIC_SCHOLAR_RETRY_MIN_WAIT_SECONDS", 1.0)
RETRY_MAX_WAIT_SECONDS = _env_float("SEMANTIC_SCHOLAR_RETRY_MAX_WAIT_SECONDS", 30.0)


def _is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, ConnectionRefusedError) and "429" in str(exc)


def _is_forbidden(exc: BaseException) -> bool:
    return isinstance(exc, PermissionError) and "403" in str(exc)


RATE_LIMIT_RETRYER = Retrying(
    retry=retry_if_exception(_is_rate_limited),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _call_with_rate_limit_retry(func: Callable[..., ResultT], *args: object, **kwargs: object) -> ResultT:
    return RATE_LIMIT_RETRYER(func, *args, **kwargs)


class SupportsLoadedItems(Protocol[ItemT]):
    @property
    def items(self) -> Sequence[ItemT]: ...


class ThrottleLike(Protocol):
    def wait_for_turn(self) -> None: ...


class AuthorLike(Protocol):
    @property
    def name(self) -> str | None: ...

    @property
    def authorId(self) -> str | None: ...

    @property
    def url(self) -> str | None: ...

    @property
    def affiliations(self) -> Sequence[str] | None: ...

    @property
    def paperCount(self) -> int | None: ...

    @property
    def citationCount(self) -> int | None: ...

    @property
    def hIndex(self) -> int | None: ...


class PaperLike(Protocol):
    @property
    def paperId(self) -> str | None: ...

    @property
    def title(self) -> str | None: ...

    @property
    def abstract(self) -> str | None: ...

    @property
    def year(self) -> int | None: ...

    @property
    def authors(self) -> Sequence[AuthorLike]: ...

    @property
    def url(self) -> str | None: ...

    @property
    def venue(self) -> str | None: ...

    @property
    def publicationTypes(self) -> Sequence[str] | None: ...

    @property
    def citationCount(self) -> int | None: ...

    @property
    def citations(self) -> Sequence["PaperLike"]: ...

    @property
    def references(self) -> Sequence["PaperLike"]: ...


class PaperSearchClient(Protocol):
    def search_paper(self, query: str, limit: int = 10) -> object: ...


class PaperDetailsClient(Protocol):
    def get_paper(self, paper_id: str) -> PaperLike: ...


class AuthorDetailsClient(Protocol):
    def get_author(self, author_id: str) -> AuthorLike: ...


class AuthorSearchClient(Protocol):
    def search_author(self, query: str, limit: int = 10) -> object: ...


class AuthorPapersClient(Protocol):
    def get_author_papers(self, author_id: str, limit: int = 100) -> object: ...


class RecommendationsClient(Protocol):
    def get_recommended_papers(
        self,
        paper_id: str,
        limit: int = 10,
        pool_from: Literal["recent", "all-cs"] = "recent",
    ) -> Sequence[PaperLike]: ...


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
                logger.debug("Waiting %.2fs to respect Semantic Scholar rate limit.", remaining)
                time.sleep(remaining)
                now = time.monotonic()
            self._last_request_started_at = now


class SemanticScholarClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or None
        self._using_api_key = bool(self._api_key)
        self._throttle: ThrottleLike = RequestThrottle(MIN_SECONDS_BETWEEN_REQUESTS)
        self._client = self._build_client(api_key=self._api_key)

    def _build_client(self, api_key: str | None = None) -> SemanticScholar:
        if api_key is None:
            return SemanticScholar(retry=False)
        return SemanticScholar(api_key=api_key, retry=False)

    def _disable_api_key(self) -> None:
        self._using_api_key = False
        self._client = self._build_client(api_key=None)

    def _call(self, method_name: str, *args: object, **kwargs: object) -> object:
        def call_once() -> object:
            self._throttle.wait_for_turn()
            method = cast(Callable[..., object], getattr(self._client, method_name))
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

    def search_paper(self, query: str, limit: int = 10) -> object:
        return self._call("search_paper", query, limit=limit)

    def get_paper(self, paper_id: str) -> PaperLike:
        return cast(PaperLike, self._call("get_paper", paper_id))

    def get_author(self, author_id: str) -> AuthorLike:
        return cast(AuthorLike, self._call("get_author", author_id))

    def search_author(self, query: str, limit: int = 10) -> object:
        return self._call("search_author", query, limit=limit)

    def get_author_papers(self, author_id: str, limit: int = 100) -> object:
        return self._call("get_author_papers", author_id, limit=limit)

    def get_recommended_papers(
        self, paper_id: str, limit: int = 10, pool_from: Literal["recent", "all-cs"] = "recent"
    ) -> Sequence[PaperLike]:
        return cast(
            Sequence[PaperLike],
            self._call("get_recommended_papers", paper_id, limit=limit, pool_from=pool_from),
        )


def initialize_client() -> SemanticScholarClient:
    """Initialize a client that can fall back to public access on 403."""
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
    return SemanticScholarClient(api_key=api_key)


def format_author_brief(author: AuthorLike) -> PaperAuthor:
    return {
        "name": author.name,
        "authorId": author.authorId,
    }


def format_paper(paper: PaperLike) -> PaperSummary:
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "authors": [format_author_brief(author) for author in paper.authors],
        "url": paper.url,
        "venue": paper.venue,
        "publicationTypes": list(paper.publicationTypes) if paper.publicationTypes is not None else None,
        "citationCount": paper.citationCount,
    }


def format_related_paper(paper: PaperLike) -> RelatedPaperSummary:
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "year": paper.year,
        "authors": [format_author_brief(author) for author in paper.authors],
    }


def format_author(author: AuthorLike) -> AuthorSummary:
    return {
        "authorId": author.authorId,
        "name": author.name,
        "url": author.url,
        "affiliations": list(author.affiliations) if author.affiliations is not None else None,
        "paperCount": author.paperCount,
        "citationCount": author.citationCount,
        "hIndex": author.hIndex,
    }


def _loaded_items(results: object) -> Iterable[object]:
    """Return only the items already loaded by the client library.

    The semanticscholar PaginatedResults iterator eagerly fetches additional
    pages during iteration, which has proven unreliable for some endpoints.
    Using `.items` keeps us on the already-fetched page returned by the
    original request.
    """
    if hasattr(results, "items"):
        return cast(SupportsLoadedItems[object], results).items
    return cast(Iterable[object], results)


def search_papers(client: PaperSearchClient, query: str, limit: int = 10) -> list[PaperSummary]:
    """Search for papers using a query string."""
    results = client.search_paper(query, limit=limit)
    return [format_paper(cast(PaperLike, paper)) for paper in _loaded_items(results)]


def search_authors(client: AuthorSearchClient, query: str, limit: int = 10) -> list[AuthorSummary]:
    """Search for authors by name."""
    results = client.search_author(query, limit=limit)
    return [format_author(cast(AuthorLike, author)) for author in _loaded_items(results)]


def get_paper_details(client: PaperDetailsClient, paper_id: str) -> PaperLike:
    """Get details of a specific paper."""
    return client.get_paper(paper_id)


def get_author_details(client: AuthorDetailsClient, author_id: str) -> AuthorLike:
    """Get details of a specific author."""
    return client.get_author(author_id)


def get_author_papers(client: AuthorPapersClient, author_id: str, limit: int = 10) -> list[PaperSummary]:
    """Get papers for a specific author."""
    results = client.get_author_papers(author_id, limit=limit)
    return [format_paper(cast(PaperLike, paper)) for paper in _loaded_items(results)]


def get_recommended_papers(
    client: RecommendationsClient,
    paper_id: str,
    limit: int = 10,
    pool_from: Literal["recent", "all-cs"] = "recent",
) -> list[PaperSummary]:
    """Get recommended papers for a seed paper."""
    results = client.get_recommended_papers(paper_id, limit=limit, pool_from=pool_from)
    return [format_paper(paper) for paper in results]


def get_citations_and_references(paper: PaperLike) -> CitationsAndReferences:
    """Get citations and references for a paper."""
    return {
        "citations": [format_related_paper(citation) for citation in paper.citations],
        "references": [format_related_paper(reference) for reference in paper.references],
    }


def main() -> None:
    try:
        client = initialize_client()

        search_results = search_papers(client, "machine learning")
        print(f"Search results: {search_results[:2]}")

        if search_results:
            paper_id = search_results[0]["paperId"]
            if paper_id is not None:
                paper = get_paper_details(client, paper_id)
                print(f"Paper details: {paper}")

                citations_refs = get_citations_and_references(paper)
                print(f"Citations: {citations_refs['citations'][:2]}")
                print(f"References: {citations_refs['references'][:2]}")

        author_id = "1741101"
        author = get_author_details(client, author_id)
        print(f"Author details: {author}")

    except Exception as exc:
        print(f"An error occurred: {exc}")


if __name__ == "__main__":
    main()
