from typing import TypeAlias

from typing_extensions import TypedDict


class ToolError(TypedDict):
    error: str


class PaperAuthor(TypedDict):
    name: str | None
    authorId: str | None


class PaperSummary(TypedDict):
    paperId: str | None
    title: str | None
    abstract: str | None
    year: int | None
    publicationDate: str | None
    authors: list[PaperAuthor]
    url: str | None
    venue: str | None
    publicationTypes: list[str] | None
    citationCount: int | None
    externalIds: dict[str, str] | None
    doi: str | None
    pmid: str | None
    arxivId: str | None


class FlexiblePaperSummary(PaperSummary, total=False):
    matchScore: float | None
    isOpenAccess: bool | None
    openAccessPdfUrl: str | None
    fieldsOfStudy: list[str] | None
    citationStyles: dict[str, str] | None
    rawData: dict[str, object]


class AuthorSummary(TypedDict):
    authorId: str | None
    name: str | None
    url: str | None
    affiliations: list[str] | None
    paperCount: int | None
    citationCount: int | None
    hIndex: int | None


class RelatedPaperSummary(TypedDict):
    paperId: str | None
    title: str | None
    abstract: str | None
    year: int | None
    publicationDate: str | None
    authors: list[PaperAuthor]
    url: str | None
    venue: str | None
    publicationTypes: list[str] | None
    citationCount: int | None
    externalIds: dict[str, str] | None
    doi: str | None
    pmid: str | None
    arxivId: str | None
    contexts: list[str] | None
    intents: list[str] | None
    isInfluential: bool | None


class RelatedPaperPage(TypedDict):
    total: int | None
    offset: int
    limit: int
    returned: int
    hasMore: bool
    items: list[RelatedPaperSummary]


class CitationsAndReferences(TypedDict):
    citations: RelatedPaperPage
    references: RelatedPaperPage


class PaperSearchPage(TypedDict):
    total: int | None
    offset: int
    next: int | None
    limit: int
    returned: int
    hasMore: bool
    items: list[FlexiblePaperSummary]


class BulkPaperSearchPage(TypedDict):
    total: int | None
    nextToken: str | None
    limit: int
    returned: int
    hasMore: bool
    sort: str | None
    items: list[FlexiblePaperSummary]


class AutocompleteSuggestion(TypedDict):
    id: str | None
    title: str | None
    authorsYear: str | None


class BibtexExport(TypedDict):
    paperId: str | None
    title: str | None
    bibtex: str | None


class SnippetPaperSummary(TypedDict, total=False):
    paperId: str | None
    corpusId: int | None
    title: str | None
    authors: list[PaperAuthor]
    year: int | None
    venue: str | None
    url: str | None
    openAccessPdfUrl: str | None
    rawData: dict[str, object]


class SnippetResultItem(TypedDict):
    score: float | None
    paper: SnippetPaperSummary
    snippet: dict[str, object]


class SnippetSearchResult(TypedDict):
    limit: int
    returned: int
    items: list[SnippetResultItem]


class RetryConfig(TypedDict):
    attempts: int
    minWaitSeconds: float
    maxWaitSeconds: float


class RequestConfig(TypedDict):
    minSecondsBetweenRequests: float
    timeoutSeconds: float
    retry: RetryConfig


class HealthStatus(TypedDict, total=False):
    version: str
    apiKeyConfigured: bool
    usingApiKey: bool
    apiReachable: bool
    timestamp: str
    requestConfig: RequestConfig
    apiError: str


PaperListResult: TypeAlias = list[PaperSummary] | list[ToolError]
FlexiblePaperListResult: TypeAlias = list[FlexiblePaperSummary] | list[ToolError]
AuthorListResult: TypeAlias = list[AuthorSummary] | list[ToolError]
AutocompleteListResult: TypeAlias = list[AutocompleteSuggestion] | list[ToolError]
BibtexListResult: TypeAlias = list[BibtexExport] | list[ToolError]
PaperDetailResult: TypeAlias = PaperSummary | ToolError
FlexiblePaperDetailResult: TypeAlias = FlexiblePaperSummary | ToolError
AuthorDetailResult: TypeAlias = AuthorSummary | ToolError
RelatedResult: TypeAlias = CitationsAndReferences | ToolError
RelatedPageResult: TypeAlias = RelatedPaperPage | ToolError
PaperSearchResult: TypeAlias = PaperSearchPage | ToolError
BulkPaperSearchResult: TypeAlias = BulkPaperSearchPage | ToolError
SnippetResult: TypeAlias = SnippetSearchResult | ToolError
HealthResult: TypeAlias = HealthStatus | ToolError
