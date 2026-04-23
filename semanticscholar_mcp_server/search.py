import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, TypeVar, cast

import requests
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
    RelatedPaperPage,
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
REQUEST_TIMEOUT_SECONDS = _env_float("SEMANTIC_SCHOLAR_REQUEST_TIMEOUT_SECONDS", 30.0)
API_BASE_URL = "https://api.semanticscholar.org"
RELATED_PAPER_FIELDS = [
    "paperId",
    "title",
    "abstract",
    "authors",
    "citationCount",
    "externalIds",
    "publicationTypes",
    "url",
    "venue",
    "year",
]
REFERENCE_METADATA_FIELDS = ["contexts", "intents", "isInfluential"]


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
    def publicationDate(self) -> str | None: ...

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
    def externalIds(self) -> dict[str, str] | None: ...

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


class PaperBatchClient(Protocol):
    def get_papers(self, paper_ids: list[str]) -> Sequence[PaperLike]: ...


class CitationsPageClient(Protocol):
    def get_paper_citations_page(self, paper_id: str, limit: int = 100, offset: int = 0) -> dict[str, object]: ...


class ReferencesPageClient(Protocol):
    def get_paper_references_page(self, paper_id: str, limit: int = 100, offset: int = 0) -> dict[str, object]: ...


class RelatedPagesClient(CitationsPageClient, ReferencesPageClient, Protocol):
    pass


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

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | float] | None = None,
    ) -> dict[str, object]:
        def call_once() -> dict[str, object]:
            self._throttle.wait_for_turn()
            headers = {"x-api-key": self._api_key} if self._using_api_key and self._api_key else None
            response = requests.request(
                method=method,
                url=f"{API_BASE_URL}{path}",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                return cast(dict[str, object], response.json())
            if response.status_code == 403:
                raise PermissionError("HTTP status 403 Forbidden.")
            if response.status_code == 429:
                raise ConnectionRefusedError("HTTP status 429 Too Many Requests.")
            raise RuntimeError(
                f"HTTP status {response.status_code}: {response.text[:300].replace(chr(10), ' ')}"
            )

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

    def get_papers(self, paper_ids: list[str]) -> Sequence[PaperLike]:
        return cast(Sequence[PaperLike], self._call("get_papers", paper_ids))

    def get_paper_citations_page(self, paper_id: str, limit: int = 100, offset: int = 0) -> dict[str, object]:
        return self._request_json(
            "GET",
            f"/graph/v1/paper/{paper_id}/citations",
            params={
                "fields": ",".join(
                    REFERENCE_METADATA_FIELDS + [f"citingPaper.{field}" for field in RELATED_PAPER_FIELDS]
                ),
                "limit": limit,
                "offset": offset,
            },
        )

    def get_paper_references_page(self, paper_id: str, limit: int = 100, offset: int = 0) -> dict[str, object]:
        return self._request_json(
            "GET",
            f"/graph/v1/paper/{paper_id}/references",
            params={
                "fields": ",".join(
                    REFERENCE_METADATA_FIELDS + [f"citedPaper.{field}" for field in RELATED_PAPER_FIELDS]
                ),
                "limit": limit,
                "offset": offset,
            },
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
    external_ids = _normalize_external_ids(getattr(paper, "externalIds", None))
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "publicationDate": paper.publicationDate,
        "authors": [format_author_brief(author) for author in paper.authors],
        "url": paper.url,
        "venue": paper.venue,
        "publicationTypes": list(paper.publicationTypes) if paper.publicationTypes is not None else None,
        "citationCount": paper.citationCount,
        "externalIds": external_ids,
        "doi": _extract_external_id(external_ids, "DOI"),
        "pmid": _extract_external_id(external_ids, "PubMed", "PMID"),
        "arxivId": _extract_external_id(external_ids, "ArXiv"),
    }


def format_related_paper(paper: PaperLike) -> RelatedPaperSummary:
    external_ids = _normalize_external_ids(getattr(paper, "externalIds", None))
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "publicationDate": paper.publicationDate,
        "authors": [format_author_brief(author) for author in paper.authors],
        "url": paper.url,
        "venue": paper.venue,
        "publicationTypes": list(paper.publicationTypes) if paper.publicationTypes is not None else None,
        "citationCount": paper.citationCount,
        "externalIds": external_ids,
        "doi": _extract_external_id(external_ids, "DOI"),
        "pmid": _extract_external_id(external_ids, "PubMed", "PMID"),
        "arxivId": _extract_external_id(external_ids, "ArXiv"),
        "contexts": None,
        "intents": None,
        "isInfluential": None,
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


def _normalize_external_ids(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    normalized = {str(key): str(raw_value) for key, raw_value in value.items() if raw_value is not None}
    return normalized or None


def _extract_external_id(external_ids: dict[str, str] | None, *candidate_keys: str) -> str | None:
    if external_ids is None:
        return None
    lowered = {key.lower(): value for key, value in external_ids.items()}
    for key in candidate_keys:
        value = lowered.get(key.lower())
        if value:
            return value
    return None


def format_reference_record(reference: dict[str, object], paper_key: str) -> RelatedPaperSummary:
    paper = cast(dict[str, object], reference.get(paper_key, {}))
    authors_raw = cast(list[dict[str, object]], paper.get("authors", []))
    publication_types = paper.get("publicationTypes")
    external_ids = _normalize_external_ids(paper.get("externalIds"))
    return {
        "paperId": cast(str | None, paper.get("paperId")),
        "title": cast(str | None, paper.get("title")),
        "abstract": cast(str | None, paper.get("abstract")),
        "year": cast(int | None, paper.get("year")),
        "publicationDate": cast(str | None, paper.get("publicationDate")),
        "authors": [
            {
                "name": cast(str | None, author.get("name")),
                "authorId": cast(str | None, author.get("authorId")),
            }
            for author in authors_raw
        ],
        "url": cast(str | None, paper.get("url")),
        "venue": cast(str | None, paper.get("venue")),
        "publicationTypes": cast(list[str] | None, publication_types),
        "citationCount": cast(int | None, paper.get("citationCount")),
        "externalIds": external_ids,
        "doi": _extract_external_id(external_ids, "DOI"),
        "pmid": _extract_external_id(external_ids, "PubMed", "PMID"),
        "arxivId": _extract_external_id(external_ids, "ArXiv"),
        "contexts": cast(list[str] | None, reference.get("contexts")),
        "intents": cast(list[str] | None, reference.get("intents")),
        "isInfluential": cast(bool | None, reference.get("isInfluential")),
    }


def _has_more(total: int | None, offset: int, returned: int, limit: int) -> bool:
    if total is None:
        return returned == limit
    return offset + returned < total


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


def get_papers_batch(client: PaperBatchClient, paper_ids: list[str]) -> list[PaperSummary]:
    """Get details for multiple papers in one request."""
    results = client.get_papers(paper_ids)
    return [format_paper(paper) for paper in results]


def get_citations_and_references(paper: PaperLike) -> CitationsAndReferences:
    """Get citations and references from an already-loaded paper object."""
    return {
        "citations": {
            "total": len(paper.citations),
            "offset": 0,
            "limit": len(paper.citations),
            "returned": len(paper.citations),
            "hasMore": False,
            "items": [format_related_paper(citation) for citation in paper.citations],
        },
        "references": {
            "total": len(paper.references),
            "offset": 0,
            "limit": len(paper.references),
            "returned": len(paper.references),
            "hasMore": False,
            "items": [format_related_paper(reference) for reference in paper.references],
        },
    }


def _validate_page_args(limit: int, offset: int) -> None:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if offset < 0:
        raise ValueError("offset must be 0 or greater")


def get_citations_page(client: CitationsPageClient, paper_id: str, limit: int = 100, offset: int = 0) -> RelatedPaperPage:
    """Get a paginated page of citations with richer paper metadata."""
    _validate_page_args(limit, offset)
    response = client.get_paper_citations_page(paper_id, limit=limit, offset=offset)
    data = cast(list[dict[str, object]], response.get("data", []))
    total = cast(int | None, response.get("total"))
    items = [format_reference_record(item, "citingPaper") for item in data]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": len(items),
        "hasMore": _has_more(total, offset, len(items), limit),
        "items": items,
    }


def get_references_page(client: ReferencesPageClient, paper_id: str, limit: int = 100, offset: int = 0) -> RelatedPaperPage:
    """Get a paginated page of references with richer paper metadata."""
    _validate_page_args(limit, offset)
    response = client.get_paper_references_page(paper_id, limit=limit, offset=offset)
    data = cast(list[dict[str, object]], response.get("data", []))
    total = cast(int | None, response.get("total"))
    items = [format_reference_record(item, "citedPaper") for item in data]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": len(items),
        "hasMore": _has_more(total, offset, len(items), limit),
        "items": items,
    }


def get_citations_and_references_page_pair(
    client: RelatedPagesClient,
    paper_id: str,
    *,
    citations_limit: int = 100,
    citations_offset: int = 0,
    references_limit: int = 100,
    references_offset: int = 0,
) -> CitationsAndReferences:
    """Get bounded pages of both citations and references."""
    return {
        "citations": get_citations_page(client, paper_id, citations_limit, citations_offset),
        "references": get_references_page(client, paper_id, references_limit, references_offset),
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
                print(f"Citations: {citations_refs['citations']['items'][:2]}")
                print(f"References: {citations_refs['references']['items'][:2]}")

        author_id = "1741101"
        author = get_author_details(client, author_id)
        print(f"Author details: {author}")

    except Exception as exc:
        print(f"An error occurred: {exc}")


if __name__ == "__main__":
    main()
