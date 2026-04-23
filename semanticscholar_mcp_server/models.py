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
    authors: list[PaperAuthor]
    url: str | None
    venue: str | None
    publicationTypes: list[str] | None
    citationCount: int | None


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
    year: int | None
    authors: list[PaperAuthor]


class CitationsAndReferences(TypedDict):
    citations: list[RelatedPaperSummary]
    references: list[RelatedPaperSummary]


PaperListResult: TypeAlias = list[PaperSummary] | list[ToolError]
AuthorListResult: TypeAlias = list[AuthorSummary] | list[ToolError]
PaperDetailResult: TypeAlias = PaperSummary | ToolError
AuthorDetailResult: TypeAlias = AuthorSummary | ToolError
RelatedResult: TypeAlias = CitationsAndReferences | ToolError
