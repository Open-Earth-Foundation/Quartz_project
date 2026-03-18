from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


SourceClass = Literal["city_root", "city_subdomain", "municipal_entity", "supporting_external", "reject_external"]


class CityTarget(BaseModel):
    city: str
    country: str
    aliases: list[str] = Field(default_factory=list)
    seed_domains: list[str] = Field(default_factory=list)

    @field_validator("aliases", "seed_domains", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    @property
    def names(self) -> list[str]:
        ordered = [self.city, *self.aliases]
        seen: set[str] = set()
        result: list[str] = []
        for item in ordered:
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


class CityBatchInput(BaseModel):
    cities: list[CityTarget]


class SearchHit(BaseModel):
    query: str
    url: str
    title: str
    snippet: str = ""
    rank_score: float = 0.0
    source_class: SourceClass = "supporting_external"


class ScrapedSource(BaseModel):
    url: str
    title: str = ""
    content: str = ""
    source_kind: Literal["html", "pdf"] = "html"
    internal_links: list[str] = Field(default_factory=list)
    supporting_pdf_urls: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    was_truncated: bool = False
    requires_ocr: bool = False
    source_class: SourceClass = "supporting_external"


class VerifiedProject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_key: str
    city: str
    country: str
    project_title: str
    summary: str = ""
    status: str
    is_active: bool
    climate_tags: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    source_class: SourceClass = Field(
        validation_alias=AliasChoices("source_class", "source_confidence"),
        serialization_alias="source_class",
    )
    supporting_pdf_urls: list[str] = Field(default_factory=list)
    funding_source: str | None = None
    funding_programme: str | None = None
    funding_amount: float | None = None
    currency: str | None = None
    funding_evidence: str = ""
    status_evidence: str = ""
    last_official_update: str | None = None
    last_verified_at: str

    @property
    def source_confidence(self) -> SourceClass:
        return self.source_class


class RejectedCandidate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    title: str = ""
    source_class: SourceClass = Field(
        validation_alias=AliasChoices("source_class", "source_confidence"),
        serialization_alias="source_class",
    )
    reason: str
    borderline: bool = False

    @property
    def source_confidence(self) -> SourceClass:
        return self.source_class


class VerificationResult(BaseModel):
    source_class: SourceClass
    accepted_projects: list[VerifiedProject] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)


class CityRunSummary(BaseModel):
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    removed_inactive: int = 0
    rejected: int = 0


class CityRunReport(BaseModel):
    city: str
    country: str
    queries: list[str] = Field(default_factory=list)
    search_hits: list[SearchHit] = Field(default_factory=list)
    accepted_projects: list[VerifiedProject] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    summary: CityRunSummary = Field(default_factory=CityRunSummary)


class BatchRunReport(BaseModel):
    generated_at: str
    registry_path: str
    review_log_path: str
    hints_log_path: str | None = None
    city_reports: list[CityRunReport] = Field(default_factory=list)
    summary: CityRunSummary = Field(default_factory=CityRunSummary)
