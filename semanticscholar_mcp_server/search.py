import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
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
    AutocompleteSuggestion,
    AuthorSummary,
    BibtexExport,
    BulkPaperSearchPage,
    CitationsAndReferences,
    FlexiblePaperSummary,
    HealthStatus,
    PaperAuthor,
    PaperSearchPage,
    PaperSummary,
    RelatedPaperPage,
    RelatedPaperSummary,
    RequestConfig,
    RetryConfig,
    SnippetPaperSummary,
    SnippetResultItem,
    SnippetSearchResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")
ItemT = TypeVar("ItemT", covariant=True)

DEFAULT_PAPER_FIELDS = [
    "title",
    "abstract",
    "authors",
    "citationCount",
    "externalIds",
    "publicationDate",
    "publicationTypes",
    "url",
    "venue",
    "year",
]
DEFAULT_ADVANCED_PAPER_FIELDS = DEFAULT_PAPER_FIELDS + ["isOpenAccess", "openAccessPdf", "fieldsOfStudy"]
DEFAULT_BULK_PAPER_FIELDS = DEFAULT_ADVANCED_PAPER_FIELDS
BIBTEX_FIELDS = ["title", "citationStyles"]
RELATED_PAPER_FIELDS = [
    "paperId",
    "title",
    "abstract",
    "authors",
    "citationCount",
    "externalIds",
    "publicationDate",
    "publicationTypes",
    "url",
    "venue",
    "year",
]
REFERENCE_METADATA_FIELDS = ["contexts", "intents", "isInfluential"]
VALID_RECOMMENDATION_POOLS = {"recent", "all-cs"}
VALID_BULK_SORT_FIELDS = {"paperId", "publicationDate", "citationCount"}


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
    def publicationDate(self) -> object | None: ...

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


class JsonRequestClient(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | float] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> object: ...


class StatusClient(JsonRequestClient, Protocol):
    @property
    def api_key_configured(self) -> bool: ...

    @property
    def using_api_key(self) -> bool: ...


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

    @property
    def api_key_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def using_api_key(self) -> bool:
        return self._using_api_key

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
        json_body: dict[str, object] | None = None,
    ) -> object:
        def call_once() -> object:
            self._throttle.wait_for_turn()
            headers = {"x-api-key": self._api_key} if self._using_api_key and self._api_key else None
            response = requests.request(
                method=method,
                url=f"{API_BASE_URL}{path}",
                params=params,
                json=json_body,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                return cast(object, response.json())
            if response.status_code == 403:
                raise PermissionError("HTTP status 403 Forbidden.")
            if response.status_code == 429:
                raise ConnectionRefusedError("HTTP status 429 Too Many Requests.")
            raise RuntimeError(f"HTTP status {response.status_code}: {response.text[:300].replace(chr(10), ' ')}")

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

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | float] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> object:
        return self._request_json(method, path, params=params, json_body=json_body)

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
        return cast(
            dict[str, object],
            self._request_json(
                "GET",
                f"/graph/v1/paper/{paper_id}/citations",
                params={
                    "fields": ",".join(
                        REFERENCE_METADATA_FIELDS + [f"citingPaper.{field}" for field in RELATED_PAPER_FIELDS]
                    ),
                    "limit": limit,
                    "offset": offset,
                },
            ),
        )

    def get_paper_references_page(self, paper_id: str, limit: int = 100, offset: int = 0) -> dict[str, object]:
        return cast(
            dict[str, object],
            self._request_json(
                "GET",
                f"/graph/v1/paper/{paper_id}/references",
                params={
                    "fields": ",".join(
                        REFERENCE_METADATA_FIELDS + [f"citedPaper.{field}" for field in RELATED_PAPER_FIELDS]
                    ),
                    "limit": limit,
                    "offset": offset,
                },
            ),
        )


def initialize_client() -> SemanticScholarClient:
    """Initialize a client that can fall back to public access on 403."""
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
    return SemanticScholarClient(api_key=api_key)


def _package_version() -> str:
    try:
        return version("semanticscholar-mcp-server")
    except PackageNotFoundError:
        return "0.1.0"


def format_author_brief(author: AuthorLike) -> PaperAuthor:
    return {
        "name": author.name,
        "authorId": author.authorId,
    }


def _normalize_publication_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_external_ids(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    normalized = {str(key): str(raw_value) for key, raw_value in value.items() if raw_value is not None}
    return normalized or None


def _normalize_citation_styles(value: object) -> dict[str, str] | None:
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


def _normalize_string_list(value: object) -> list[str] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    normalized = [str(item) for item in value if item is not None]
    return normalized or None


def _format_author_briefs_from_mapping(authors: object) -> list[PaperAuthor]:
    if not isinstance(authors, Sequence) or isinstance(authors, (str, bytes)):
        return []
    items: list[PaperAuthor] = []
    for author in authors:
        if not isinstance(author, Mapping):
            continue
        items.append(
            {
                "name": cast(str | None, author.get("name")),
                "authorId": cast(str | None, author.get("authorId")),
            }
        )
    return items


def _normalize_fields_of_study(record: Mapping[str, object]) -> list[str] | None:
    direct = _normalize_string_list(record.get("fieldsOfStudy"))
    if direct is not None:
        return direct
    s2_fields = record.get("s2FieldsOfStudy")
    if not isinstance(s2_fields, Sequence) or isinstance(s2_fields, (str, bytes)):
        return None
    normalized = []
    for item in s2_fields:
        if isinstance(item, Mapping):
            category = item.get("category")
            if category is not None:
                normalized.append(str(category))
    return normalized or None


def _extract_open_access_pdf_url(record: Mapping[str, object]) -> str | None:
    open_access_pdf = record.get("openAccessPdf")
    if isinstance(open_access_pdf, Mapping):
        url = open_access_pdf.get("url")
        if url is not None:
            return str(url)
    open_access_info = record.get("openAccessInfo")
    if isinstance(open_access_info, Mapping):
        nested_pdf = open_access_info.get("openAccessPdf")
        if isinstance(nested_pdf, Mapping):
            url = nested_pdf.get("url")
            if url is not None:
                return str(url)
    return None


def _format_paper_summary_from_mapping(record: Mapping[str, object]) -> PaperSummary:
    external_ids = _normalize_external_ids(record.get("externalIds"))
    return {
        "paperId": cast(str | None, record.get("paperId")),
        "title": cast(str | None, record.get("title")),
        "abstract": cast(str | None, record.get("abstract")),
        "year": cast(int | None, record.get("year")),
        "publicationDate": _normalize_publication_date(record.get("publicationDate")),
        "authors": _format_author_briefs_from_mapping(record.get("authors")),
        "url": cast(str | None, record.get("url")),
        "venue": cast(str | None, record.get("venue")),
        "publicationTypes": _normalize_string_list(record.get("publicationTypes")),
        "citationCount": cast(int | None, record.get("citationCount")),
        "externalIds": external_ids,
        "doi": _extract_external_id(external_ids, "DOI"),
        "pmid": _extract_external_id(external_ids, "PubMed", "PMID"),
        "arxivId": _extract_external_id(external_ids, "ArXiv"),
    }


def format_paper(paper: PaperLike) -> PaperSummary:
    external_ids = _normalize_external_ids(getattr(paper, "externalIds", None))
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "publicationDate": _normalize_publication_date(paper.publicationDate),
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


def format_paper_record(record: Mapping[str, object], *, include_raw_data: bool = False) -> FlexiblePaperSummary:
    result = cast(FlexiblePaperSummary, _format_paper_summary_from_mapping(record))
    match_score = record.get("matchScore")
    if match_score is not None:
        result["matchScore"] = cast(float | None, match_score)
    if "isOpenAccess" in record:
        result["isOpenAccess"] = cast(bool | None, record.get("isOpenAccess"))
    open_access_pdf_url = _extract_open_access_pdf_url(record)
    if open_access_pdf_url is not None:
        result["openAccessPdfUrl"] = open_access_pdf_url
    fields_of_study = _normalize_fields_of_study(record)
    if fields_of_study is not None:
        result["fieldsOfStudy"] = fields_of_study
    citation_styles = _normalize_citation_styles(record.get("citationStyles"))
    if citation_styles is not None:
        result["citationStyles"] = citation_styles
    if include_raw_data:
        result["rawData"] = dict(record)
    return result


def format_related_paper(paper: PaperLike) -> RelatedPaperSummary:
    external_ids = _normalize_external_ids(getattr(paper, "externalIds", None))
    return {
        "paperId": paper.paperId,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "publicationDate": _normalize_publication_date(paper.publicationDate),
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


def format_author_record(author: Mapping[str, object]) -> AuthorSummary:
    return {
        "authorId": cast(str | None, author.get("authorId")),
        "name": cast(str | None, author.get("name")),
        "url": cast(str | None, author.get("url")),
        "affiliations": _normalize_string_list(author.get("affiliations")),
        "paperCount": cast(int | None, author.get("paperCount")),
        "citationCount": cast(int | None, author.get("citationCount")),
        "hIndex": cast(int | None, author.get("hIndex")),
    }


def format_reference_record(reference: dict[str, object], paper_key: str) -> RelatedPaperSummary:
    paper = cast(dict[str, object], reference.get(paper_key, {}))
    paper_summary = _format_paper_summary_from_mapping(paper)
    return {
        **paper_summary,
        "contexts": cast(list[str] | None, reference.get("contexts")),
        "intents": cast(list[str] | None, reference.get("intents")),
        "isInfluential": cast(bool | None, reference.get("isInfluential")),
    }


def format_bibtex_export(record: Mapping[str, object]) -> BibtexExport:
    citation_styles = _normalize_citation_styles(record.get("citationStyles"))
    return {
        "paperId": cast(str | None, record.get("paperId")),
        "title": cast(str | None, record.get("title")),
        "bibtex": citation_styles.get("bibtex") if citation_styles is not None else None,
    }


def format_snippet_record(record: Mapping[str, object], *, include_raw_paper: bool = False) -> SnippetResultItem:
    paper_raw = cast(Mapping[str, object], record.get("paper", {}))
    paper: SnippetPaperSummary = {
        "paperId": cast(str | None, paper_raw.get("paperId")),
        "corpusId": cast(int | None, paper_raw.get("corpusId")),
        "title": cast(str | None, paper_raw.get("title")),
        "authors": _format_author_briefs_from_mapping(paper_raw.get("authors")),
        "year": cast(int | None, paper_raw.get("year")),
        "venue": cast(str | None, paper_raw.get("venue")),
        "url": cast(str | None, paper_raw.get("url")),
    }
    open_access_pdf_url = _extract_open_access_pdf_url(paper_raw)
    if open_access_pdf_url is not None:
        paper["openAccessPdfUrl"] = open_access_pdf_url
    if include_raw_paper:
        paper["rawData"] = dict(paper_raw)
    return {
        "score": cast(float | None, record.get("score")),
        "paper": paper,
        "snippet": cast(dict[str, object], record.get("snippet", {})),
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


def _validate_limit(name: str, limit: int, *, max_limit: int) -> None:
    if limit < 1 or limit > max_limit:
        raise ValueError(f"{name} must be between 1 and {max_limit}")


def _validate_offset(offset: int) -> None:
    if offset < 0:
        raise ValueError("offset must be 0 or greater")


def _validate_non_empty_query(query: str) -> None:
    if not query.strip():
        raise ValueError("query must not be empty")


def _clean_string_values(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [value.strip() for value in values if value.strip()]
    return cleaned or None


def _csv_or_none(values: Sequence[str] | None) -> str | None:
    cleaned = _clean_string_values(values)
    if cleaned is None:
        return None
    return ",".join(cleaned)


def _normalize_fields(fields: Sequence[str] | None) -> list[str] | None:
    return _clean_string_values(fields)


def _resolve_year_filter(year: str | None, start_year: int | None = None, end_year: int | None = None) -> str | None:
    if year is not None and (start_year is not None or end_year is not None):
        raise ValueError("Specify either year or start_year/end_year, not both")
    if year is not None:
        normalized = year.strip()
        if not normalized:
            raise ValueError("year must not be empty")
        return normalized
    if start_year is None and end_year is None:
        return None
    if start_year is not None and end_year is not None and start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")
    if start_year is not None and start_year < 0:
        raise ValueError("start_year must be 0 or greater")
    if end_year is not None and end_year < 0:
        raise ValueError("end_year must be 0 or greater")
    if start_year is not None and end_year is not None:
        return f"{start_year}-{end_year}"
    if start_year is not None:
        return f"{start_year}-"
    return f"-{end_year}"


def _validate_sort(sort: str | None) -> str | None:
    if sort is None:
        return None
    normalized = sort.strip()
    if not normalized:
        raise ValueError("sort must not be empty")
    field, separator, order = normalized.partition(":")
    if field not in VALID_BULK_SORT_FIELDS:
        allowed = ", ".join(sorted(VALID_BULK_SORT_FIELDS))
        raise ValueError(f"sort field must be one of: {allowed}")
    if separator and order not in {"asc", "desc"}:
        raise ValueError("sort order must be 'asc' or 'desc'")
    return normalized


def _validate_identifier_list(name: str, identifiers: Sequence[str], *, max_items: int) -> list[str]:
    cleaned = _clean_string_values(identifiers)
    if cleaned is None:
        raise ValueError(f"{name} must not be empty")
    if len(cleaned) > max_items:
        raise ValueError(f"{name} must contain at most {max_items} items")
    return cleaned


def _build_relevance_search_params(
    *,
    query: str,
    limit: int,
    offset: int,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> dict[str, str | int | float]:
    _validate_non_empty_query(query)
    _validate_limit("limit", limit, max_limit=100)
    _validate_offset(offset)
    params: dict[str, str | int | float] = {
        "query": query,
        "limit": limit,
        "offset": offset,
    }
    year_filter = _resolve_year_filter(year, start_year, end_year)
    if year_filter is not None:
        params["year"] = year_filter
    fields_of_study_param = _csv_or_none(fields_of_study)
    if fields_of_study_param is not None:
        params["fieldsOfStudy"] = fields_of_study_param
    publication_types_param = _csv_or_none(publication_types)
    if publication_types_param is not None:
        params["publicationTypes"] = publication_types_param
    if open_access_only:
        params["openAccessPdf"] = ""
    if min_citation_count is not None:
        params["minCitationCount"] = min_citation_count
    fields_param = _csv_or_none(_normalize_fields(fields))
    if fields_param is not None:
        params["fields"] = fields_param
    return params


def _build_bulk_search_params(
    *,
    query: str,
    limit: int,
    token: str | None = None,
    sort: str | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> dict[str, str | int | float]:
    _validate_non_empty_query(query)
    _validate_limit("limit", limit, max_limit=1000)
    params: dict[str, str | int | float] = {
        "query": query,
        "limit": limit,
    }
    if token is not None:
        normalized_token = token.strip()
        if not normalized_token:
            raise ValueError("token must not be empty")
        params["token"] = normalized_token
    sort_param = _validate_sort(sort)
    if sort_param is not None:
        params["sort"] = sort_param
    year_filter = _resolve_year_filter(year, start_year, end_year)
    if year_filter is not None:
        params["year"] = year_filter
    fields_of_study_param = _csv_or_none(fields_of_study)
    if fields_of_study_param is not None:
        params["fieldsOfStudy"] = fields_of_study_param
    publication_types_param = _csv_or_none(publication_types)
    if publication_types_param is not None:
        params["publicationTypes"] = publication_types_param
    if open_access_only:
        params["openAccessPdf"] = ""
    if min_citation_count is not None:
        params["minCitationCount"] = min_citation_count
    fields_param = _csv_or_none(_normalize_fields(fields))
    if fields_param is not None:
        params["fields"] = fields_param
    return params


def _build_title_match_params(
    *,
    query: str,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> dict[str, str | int | float]:
    params = _build_relevance_search_params(
        query=query,
        limit=1,
        offset=0,
        year=year,
        start_year=start_year,
        end_year=end_year,
        fields_of_study=fields_of_study,
        publication_types=publication_types,
        open_access_only=open_access_only,
        min_citation_count=min_citation_count,
        fields=fields,
    )
    params.pop("limit", None)
    params.pop("offset", None)
    return params


def _build_snippet_search_params(
    *,
    query: str,
    limit: int,
    paper_ids: Sequence[str] | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> dict[str, str | int | float]:
    _validate_non_empty_query(query)
    _validate_limit("limit", limit, max_limit=1000)
    params: dict[str, str | int | float] = {
        "query": query,
        "limit": limit,
    }
    cleaned_paper_ids = _clean_string_values(paper_ids)
    if cleaned_paper_ids is not None:
        if len(cleaned_paper_ids) > 100:
            raise ValueError("paper_ids must contain at most 100 items")
        params["paperIds"] = ",".join(cleaned_paper_ids)
    year_filter = _resolve_year_filter(year, start_year, end_year)
    if year_filter is not None:
        params["year"] = year_filter
    fields_of_study_param = _csv_or_none(fields_of_study)
    if fields_of_study_param is not None:
        params["fieldsOfStudy"] = fields_of_study_param
    if min_citation_count is not None:
        params["minCitationCount"] = min_citation_count
    fields_param = _csv_or_none(_normalize_fields(fields))
    if fields_param is not None:
        params["fields"] = fields_param
    return params


def search_papers(client: PaperSearchClient, query: str, limit: int = 10) -> list[PaperSummary]:
    """Search for papers using a query string."""
    results = client.search_paper(query, limit=limit)
    return [format_paper(cast(PaperLike, paper)) for paper in _loaded_items(results)]


def search_papers_advanced(
    client: JsonRequestClient,
    query: str,
    *,
    limit: int = 10,
    offset: int = 0,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> PaperSearchPage:
    params = _build_relevance_search_params(
        query=query,
        limit=limit,
        offset=offset,
        year=year,
        start_year=start_year,
        end_year=end_year,
        fields_of_study=fields_of_study,
        publication_types=publication_types,
        open_access_only=open_access_only,
        min_citation_count=min_citation_count,
        fields=fields or DEFAULT_ADVANCED_PAPER_FIELDS,
    )
    response = cast(dict[str, object], client.request_json("GET", "/graph/v1/paper/search", params=params))
    data = cast(list[dict[str, object]], response.get("data", []))
    include_raw_data = fields is not None
    items = [format_paper_record(item, include_raw_data=include_raw_data) for item in data]
    total = cast(int | None, response.get("total"))
    next_offset = cast(int | None, response.get("next"))
    return {
        "total": total,
        "offset": cast(int, response.get("offset", offset)),
        "next": next_offset,
        "limit": limit,
        "returned": len(items),
        "hasMore": next_offset is not None if next_offset is not None else _has_more(total, offset, len(items), limit),
        "items": items,
    }


def search_papers_bulk(
    client: JsonRequestClient,
    query: str,
    *,
    limit: int = 100,
    token: str | None = None,
    sort: str | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> BulkPaperSearchPage:
    params = _build_bulk_search_params(
        query=query,
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
        fields=fields or DEFAULT_BULK_PAPER_FIELDS,
    )
    response = cast(dict[str, object], client.request_json("GET", "/graph/v1/paper/search/bulk", params=params))
    data = cast(list[dict[str, object]], response.get("data", []))
    include_raw_data = fields is not None
    items = [format_paper_record(item, include_raw_data=include_raw_data) for item in data]
    next_token = cast(str | None, response.get("token"))
    return {
        "total": cast(int | None, response.get("total")),
        "nextToken": next_token,
        "limit": limit,
        "returned": len(items),
        "hasMore": bool(next_token),
        "sort": _validate_sort(sort),
        "items": items,
    }


def get_paper_title_match(
    client: JsonRequestClient,
    query: str,
    *,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    publication_types: Sequence[str] | None = None,
    open_access_only: bool = False,
    min_citation_count: int | None = None,
    fields: Sequence[str] | None = None,
) -> FlexiblePaperSummary:
    params = _build_title_match_params(
        query=query,
        year=year,
        start_year=start_year,
        end_year=end_year,
        fields_of_study=fields_of_study,
        publication_types=publication_types,
        open_access_only=open_access_only,
        min_citation_count=min_citation_count,
        fields=fields or DEFAULT_ADVANCED_PAPER_FIELDS,
    )
    response = cast(dict[str, object], client.request_json("GET", "/graph/v1/paper/search/match", params=params))
    return format_paper_record(response, include_raw_data=fields is not None)


def get_paper_autocomplete(
    client: JsonRequestClient,
    query: str,
    *,
    limit: int = 10,
) -> list[AutocompleteSuggestion]:
    _validate_non_empty_query(query)
    _validate_limit("limit", limit, max_limit=100)
    response = cast(
        dict[str, object], client.request_json("GET", "/graph/v1/paper/autocomplete", params={"query": query})
    )
    matches = cast(list[dict[str, object]], response.get("matches", []))
    suggestions: list[AutocompleteSuggestion] = [
        {
            "id": cast(str | None, match.get("id")),
            "title": cast(str | None, match.get("title")),
            "authorsYear": cast(str | None, match.get("authorsYear")),
        }
        for match in matches[:limit]
    ]
    return suggestions


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


def get_authors_batch(
    client: JsonRequestClient,
    author_ids: Sequence[str],
    *,
    fields: Sequence[str] | None = None,
) -> list[AuthorSummary]:
    cleaned_author_ids = _validate_identifier_list("author_ids", author_ids, max_items=1000)
    params: dict[str, str | int | float] | None = None
    fields_param = _csv_or_none(_normalize_fields(fields))
    if fields_param is not None:
        params = {"fields": fields_param}
    response = cast(
        list[dict[str, object]],
        client.request_json("POST", "/graph/v1/author/batch", params=params, json_body={"ids": cleaned_author_ids}),
    )
    return [format_author_record(author) for author in response]


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


def get_multi_recommended_papers(
    client: JsonRequestClient,
    positive_paper_ids: Sequence[str],
    *,
    negative_paper_ids: Sequence[str] | None = None,
    limit: int = 25,
    fields: Sequence[str] | None = None,
) -> list[FlexiblePaperSummary]:
    _validate_limit("limit", limit, max_limit=500)
    positives = _validate_identifier_list("positive_paper_ids", positive_paper_ids, max_items=500)
    negatives = None
    if negative_paper_ids is not None:
        negatives = _validate_identifier_list("negative_paper_ids", negative_paper_ids, max_items=500)
    params: dict[str, str | int | float] = {
        "limit": limit,
        "fields": _csv_or_none(_normalize_fields(fields or DEFAULT_ADVANCED_PAPER_FIELDS)) or "",
    }
    body: dict[str, object] = {"positivePaperIds": positives}
    if negatives is not None:
        body["negativePaperIds"] = negatives
    response = cast(
        dict[str, object],
        client.request_json("POST", "/recommendations/v1/papers/", params=params, json_body=body),
    )
    recommended = cast(list[dict[str, object]], response.get("recommendedPapers", []))
    include_raw_data = fields is not None
    return [format_paper_record(paper, include_raw_data=include_raw_data) for paper in recommended]


def get_papers_batch(client: PaperBatchClient, paper_ids: list[str]) -> list[PaperSummary]:
    """Get details for multiple papers in one request."""
    results = client.get_papers(paper_ids)
    return [format_paper(paper) for paper in results]


def get_bibtex_exports(client: JsonRequestClient, paper_ids: Sequence[str]) -> list[BibtexExport]:
    cleaned_paper_ids = _validate_identifier_list("paper_ids", paper_ids, max_items=500)
    response = cast(
        list[dict[str, object]],
        client.request_json(
            "POST",
            "/graph/v1/paper/batch",
            params={"fields": ",".join(BIBTEX_FIELDS)},
            json_body={"ids": cleaned_paper_ids},
        ),
    )
    return [format_bibtex_export(record) for record in response]


def search_snippets(
    client: JsonRequestClient,
    query: str,
    *,
    paper_ids: Sequence[str] | None = None,
    year: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    fields_of_study: Sequence[str] | None = None,
    min_citation_count: int | None = None,
    limit: int = 10,
    fields: Sequence[str] | None = None,
) -> SnippetSearchResult:
    params = _build_snippet_search_params(
        query=query,
        limit=limit,
        paper_ids=paper_ids,
        year=year,
        start_year=start_year,
        end_year=end_year,
        fields_of_study=fields_of_study,
        min_citation_count=min_citation_count,
        fields=fields,
    )
    response = cast(dict[str, object], client.request_json("GET", "/graph/v1/snippet/search", params=params))
    data = cast(list[dict[str, object]], response.get("data", []))
    include_raw_paper = fields is not None
    items = [format_snippet_record(item, include_raw_paper=include_raw_paper) for item in data]
    return {
        "limit": limit,
        "returned": len(items),
        "items": items,
    }


def get_server_status(client: StatusClient) -> HealthStatus:
    retry_config: RetryConfig = {
        "attempts": RETRY_ATTEMPTS,
        "minWaitSeconds": RETRY_MIN_WAIT_SECONDS,
        "maxWaitSeconds": RETRY_MAX_WAIT_SECONDS,
    }
    request_config: RequestConfig = {
        "minSecondsBetweenRequests": MIN_SECONDS_BETWEEN_REQUESTS,
        "timeoutSeconds": REQUEST_TIMEOUT_SECONDS,
        "retry": retry_config,
    }
    status: HealthStatus = {
        "version": _package_version(),
        "apiKeyConfigured": client.api_key_configured,
        "usingApiKey": client.using_api_key,
        "apiReachable": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requestConfig": request_config,
    }
    try:
        client.request_json("GET", "/graph/v1/paper/search", params={"query": "semantic scholar", "limit": 1})
        status["apiReachable"] = True
        status["usingApiKey"] = client.using_api_key
    except Exception as exc:
        status["apiError"] = str(exc)
        status["usingApiKey"] = client.using_api_key
    return status


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
    _validate_limit("limit", limit, max_limit=1000)
    _validate_offset(offset)


def get_citations_page(
    client: CitationsPageClient, paper_id: str, limit: int = 100, offset: int = 0
) -> RelatedPaperPage:
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


def get_references_page(
    client: ReferencesPageClient, paper_id: str, limit: int = 100, offset: int = 0
) -> RelatedPaperPage:
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
