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


PaperListResult: TypeAlias = list[PaperSummary] | list[ToolError]
AuthorListResult: TypeAlias = list[AuthorSummary] | list[ToolError]
PaperDetailResult: TypeAlias = PaperSummary | ToolError
AuthorDetailResult: TypeAlias = AuthorSummary | ToolError
RelatedResult: TypeAlias = CitationsAndReferences | ToolError
RelatedPageResult: TypeAlias = RelatedPaperPage | ToolError
