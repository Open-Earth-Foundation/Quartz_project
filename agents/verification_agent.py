from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

import config
from pydantic import AliasChoices, BaseModel, Field

from .runtime import load_prompt, now_utc_iso, slugify
from .sdk_bridge import get_sdk, sdk_available
from .search import CITY_ECOSYSTEM_CLASSES, classify_source_class
from .types import CityTarget, RejectedCandidate, ScrapedSource, SourceClass, VerificationResult, VerifiedProject

logger = logging.getLogger(__name__)

VERIFICATION_FUNDING_HINTS = (
    "funded by",
    " is funded",
    "funded project",
    "received funding",
    "received co-financing",
    "co-financed",
    "cofinanced",
    "financed by",
    "grant from",
    "grant programme",
    "grant program",
    "financial support",
    "refund from",
    "erdf",
    "dofinansow",
    "dotacja",
    "refund",
    "otrzymał dofinansowanie",
    "otrzymała dofinansowanie",
    "otrzymało dofinansowanie",
    "uzyskał dofinansowanie",
    "uzyskała dofinansowanie",
    "uzyskało dofinansowanie",
    "umowa o dofinansowanie",
    "city budget",
    "budżetu miasta",
    "budget of the city",
)


class VerificationAgent:
    def __init__(self) -> None:
        self.prompt = load_prompt("verification.md")

    async def verify_source(self, city_target: CityTarget, source: ScrapedSource) -> VerificationResult:
        source_class = classify_source_class(source.url, city_target, source.title, source.content)
        source.source_class = source_class
        if source.requires_ocr or source_class not in CITY_ECOSYSTEM_CLASSES or self._reject_non_project_page(source):
            return self._verify_with_heuristics(city_target, source, source_class)
        if sdk_available() and source.content:
            live = await self._verify_with_sdk(city_target, source, source_class)
            if live is not None:
                if live.accepted_projects:
                    return live
                heuristic = self._verify_with_heuristics(city_target, source, source_class)
                if heuristic.accepted_projects:
                    return VerificationResult(
                        source_class=source_class,
                        accepted_projects=heuristic.accepted_projects,
                        rejected_candidates=live.rejected_candidates,
                    )
                return live
        return self._verify_with_heuristics(city_target, source, source_class)

    async def _verify_with_sdk(
        self,
        city_target: CityTarget,
        source: ScrapedSource,
        source_class: SourceClass,
    ) -> VerificationResult | None:
        sdk = get_sdk()

        class SdkProject(BaseModel):
            project_title: str
            summary: str = ""
            status: str
            is_active: bool
            climate_tags: list[str] = []
            funding_source: str | None = None
            funding_programme: str | None = None
            funding_amount: float | None = None
            currency: str | None = None
            funding_evidence: str = ""
            status_evidence: str = ""
            last_official_update: str | None = None

        class SdkRejected(BaseModel):
            title: str = ""
            reason: str
            borderline: bool = False

        class SourceDecision(BaseModel):
            source_class: str = Field(validation_alias=AliasChoices("source_class", "source_confidence"))
            accepted_projects: list[SdkProject] = []
            rejected_candidates: list[SdkRejected] = []

        prompt = self.prompt.format(
            city=city_target.city,
            country=city_target.country,
            source_url=source.url,
            source_title=source.title or "unknown",
            source_class=source_class,
            source_kind=source.source_kind,
        )
        agent = sdk.Agent(
            name="Project Verification Agent",
            instructions=prompt,
            output_type=SourceDecision,
            model=config.OPENROUTER_MODEL,
            model_settings=sdk.ModelSettings(temperature=config.VERIFICATION_AGENT_TEMPERATURE),
        )
        try:
            result = await sdk.Runner.run(agent, input=source.content[: config.MAX_INPUT_CHARS_PER_SOURCE])
            payload = result.final_output
            normalized_source_class = self._normalize_source_class(payload.source_class, fallback=source_class)
            if normalized_source_class not in CITY_ECOSYSTEM_CLASSES:
                return VerificationResult(
                    source_class=normalized_source_class,
                    accepted_projects=[],
                    rejected_candidates=[
                        RejectedCandidate(
                            url=source.url,
                            title=source.title,
                            source_class=normalized_source_class,
                            reason="External-only source cannot verify a registry record by itself.",
                            borderline=True,
                        )
                    ],
                )
            accepted: list[VerifiedProject] = []
            rejected: list[RejectedCandidate] = []
            for item in payload.accepted_projects:
                if not item.is_active:
                    continue
                item_payload = item.model_dump()
                if not self._sdk_payload_is_plausible(item_payload, source):
                    rejected.append(
                        RejectedCandidate(
                            url=source.url,
                            title=item.project_title or source.title,
                            source_class=normalized_source_class,
                            reason="SDK extraction lacked a specific climate/funding signal for a final registry record.",
                            borderline=True,
                        )
                    )
                    continue
                accepted.append(self._to_verified_project(city_target, source, normalized_source_class, item_payload))
            rejected = [
                RejectedCandidate(
                    url=source.url,
                    title=item.title or source.title,
                    source_class=normalized_source_class,
                    reason=item.reason,
                    borderline=item.borderline,
                )
                for item in payload.rejected_candidates
            ] + rejected
            return VerificationResult(
                source_class=normalized_source_class, accepted_projects=accepted, rejected_candidates=rejected
            )
        except Exception as exc:  # pragma: no cover - live path
            logger.warning("VerificationAgent fallback for %s: %s", source.url, exc)
            return None

    def _verify_with_heuristics(
        self,
        city_target: CityTarget,
        source: ScrapedSource,
        source_class: SourceClass,
    ) -> VerificationResult:
        text = f"{source.title}\n{source.content}".lower()
        funded = self._has_funding_signal(text)
        climate_tags = self._extract_climate_tags(text)
        climate = self._has_climate_relevance(text, climate_tags)
        active = self._has_active_signal(text, funded)
        inactive = self._has_inactive_signal(text, active)

        if source.requires_ocr:
            return VerificationResult(
                source_class=source_class,
                rejected_candidates=[
                    RejectedCandidate(
                        url=source.url,
                        title=source.title,
                        source_class=source_class,
                        reason="PDF requires OCR; stored only as supporting source.",
                        borderline=source_class in CITY_ECOSYSTEM_CLASSES,
                    )
                ],
            )

        if source_class == "reject_external":
            return VerificationResult(
                source_class=source_class,
                rejected_candidates=[
                    RejectedCandidate(
                        url=source.url,
                        title=source.title,
                        source_class=source_class,
                        reason="Rejected external source outside the city ecosystem.",
                        borderline=False,
                    )
                ],
            )

        if source_class == "supporting_external":
            return VerificationResult(
                source_class=source_class,
                rejected_candidates=[
                    RejectedCandidate(
                        url=source.url,
                        title=source.title,
                        source_class=source_class,
                        reason="External-only source needs municipal confirmation before inclusion.",
                        borderline=True,
                    )
                ],
            )

        page_shape_issue = self._reject_non_project_page(source)
        if page_shape_issue:
            return VerificationResult(
                source_class=source_class,
                rejected_candidates=[
                    RejectedCandidate(
                        url=source.url,
                        title=source.title,
                        source_class=source_class,
                        reason=page_shape_issue,
                        borderline=source_class in CITY_ECOSYSTEM_CLASSES,
                    )
                ],
            )

        if not funded or not climate or inactive or not active:
            reasons = []
            if not funded:
                reasons.append("missing funding signal")
            if not climate:
                reasons.append("missing climate signal")
            if inactive:
                reasons.append("inactive/completed signal")
            if not active:
                reasons.append("missing active signal")
            return VerificationResult(
                source_class=source_class,
                rejected_candidates=[
                    RejectedCandidate(
                        url=source.url,
                        title=source.title,
                        source_class=source_class,
                        reason=", ".join(reasons),
                        borderline=source_class in CITY_ECOSYSTEM_CLASSES,
                    )
                ],
            )

        project = self._to_verified_project(
            city_target,
            source,
            source_class,
            {
                "project_title": self._extract_title(source),
                "summary": self._extract_summary(source.content),
                "status": self._extract_status(text),
                "is_active": True,
                "climate_tags": climate_tags,
                "funding_source": self._extract_funding_source(source.content),
                "funding_programme": self._extract_programme(source.content),
                "funding_amount": self._extract_amount(source.content),
                "currency": self._extract_currency(source.content),
                "funding_evidence": self._extract_evidence(source.content, VERIFICATION_FUNDING_HINTS),
                "status_evidence": self._extract_evidence(source.content, config.ACTIVE_STATUS_HINTS),
                "last_official_update": self._extract_date(source.content),
            },
        )
        return VerificationResult(source_class=source_class, accepted_projects=[project], rejected_candidates=[])

    def _to_verified_project(
        self,
        city_target: CityTarget,
        source: ScrapedSource,
        source_class: SourceClass,
        payload: dict,
    ) -> VerifiedProject:
        title = payload["project_title"].strip()
        return VerifiedProject(
            project_key=f"{slugify(city_target.city)}::{slugify(title)}",
            city=city_target.city,
            country=city_target.country,
            project_title=title,
            summary=payload.get("summary", "").strip(),
            status=payload.get("status", "active"),
            is_active=bool(payload.get("is_active", True)),
            climate_tags=list(dict.fromkeys(payload.get("climate_tags", []))),
            source_urls=[source.url],
            source_class=source_class,
            supporting_pdf_urls=list(dict.fromkeys(source.supporting_pdf_urls)),
            funding_source=payload.get("funding_source"),
            funding_programme=payload.get("funding_programme"),
            funding_amount=payload.get("funding_amount"),
            currency=payload.get("currency"),
            funding_evidence=payload.get("funding_evidence", ""),
            status_evidence=payload.get("status_evidence", ""),
            last_official_update=payload.get("last_official_update"),
            last_verified_at=now_utc_iso(),
        )

    @staticmethod
    def _extract_title(source: ScrapedSource) -> str:
        if source.title:
            return VerificationAgent._clean_title(source.title)
        for line in source.content.splitlines():
            clean = line.strip().lstrip("#").strip()
            if clean:
                return VerificationAgent._clean_title(clean)
        return VerificationAgent._clean_title(source.url.rsplit("/", 1)[-1])

    @staticmethod
    def _extract_summary(content: str) -> str:
        noise_markers = (
            "cookie",
            "cookies",
            "zarządzaj zgodami",
            "functional cookies",
            "marketing",
            "statystyka",
            "privacy",
            "polityka prywatności",
            "przejdź do",
            "skip to content",
            "opis obrazka",
            "sign in",
        )
        parts = [part.strip() for part in re.split(r"\n{2,}", content) if part.strip()]
        for part in parts:
            lowered = part.lower()
            if any(marker in lowered for marker in noise_markers):
                continue
            if part.startswith("- [") and part.count("](") >= 2:
                continue
            if part.startswith("![") and "](" in part:
                continue
            if len(part) > 40:
                return part[:500]
        for part in parts:
            lowered = part.lower()
            if any(marker in lowered for marker in noise_markers):
                continue
            if part.startswith("- [") and part.count("](") >= 2:
                continue
            if part:
                return part[:500]
        return ""

    @staticmethod
    def _extract_status(text: str) -> str:
        if any(token in text for token in ("under construction", "in implementation", "ongoing", "realizacja")):
            return "in_implementation"
        return "active"

    @staticmethod
    def _extract_climate_tags(text: str) -> list[str]:
        tag_map = {
            "adaptation": ("adaptation", "adaptacji", "adaptacja do zmian klimatu", "adaptacja klimatyczna", "retenc", "stormwater", "rainwater", "flood", "resilience", "heat island", "błękitno-ziel", "co-adapt", "zielone enklawy"),
            "mobility": ("transport", "tram", "tramwaj", "bus", "mobility", "rower", "bike", "cycling", "public transport", "metro", "buspas"),
            "energy": ("solar", "fotowolta", "pv", "heat pump", "district heating", "efficiency", "energi", "renewable", "oświetlen", "termomodern"),
            "air_quality": ("air quality", "powietrz", "emission", "zero emission", "clean air", "smog"),
            "waste_water": ("wastewater", "ściek", "kanaliz", "drainage", "deszczow", "retention tank"),
            "waste": ("waste", "odpady", "recycling", "landfill", "compost"),
        }
        return [tag for tag, signals in tag_map.items() if any(signal in text for signal in signals)]

    @staticmethod
    def _has_climate_relevance(text: str, climate_tags: list[str]) -> bool:
        if any(tag in climate_tags for tag in ("adaptation", "energy", "air_quality", "waste_water", "waste")):
            return True
        if "mobility" in climate_tags and any(
            token in text
            for token in ("tram", "tramwaj", "bus", "public transport", "rower", "bike", "cycling", "zero emission", "powietrz", "emission")
        ):
            return True
        return any(
            token in text
            for token in (
                "climate city contract",
                "net zero",
                "zero emission",
                "climate neutrality",
                "neutraln",
                "decarbon",
                "food wave",
                "żywność i klimat",
            )
        )

    @staticmethod
    def _has_active_signal(text: str, funded: bool) -> bool:
        if any(token in text for token in config.ACTIVE_STATUS_HINTS):
            return True
        if not funded:
            return False
        return any(
            token in text
            for token in (
                "umowa o dofinansowanie",
                "podpisana",
                "otrzymał dofinansowanie",
                "otrzymała dofinansowanie",
                "otrzymało dofinansowanie",
                "uzyskał",
                "uzyskała",
                "uzyskało",
                "mieszkańcy otrzymają",
                "project will",
                "will include",
                "project includes",
                "w ramach projektu",
                "zakres projektu",
                "przebudowa",
                "modernizacja",
                "budowa",
            )
        )

    @staticmethod
    def _has_funding_signal(text: str) -> bool:
        return any(token in text for token in VERIFICATION_FUNDING_HINTS)

    def _sdk_payload_is_plausible(self, payload: dict, source: ScrapedSource) -> bool:
        title = str(payload.get("project_title", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        climate_tags = [str(tag) for tag in payload.get("climate_tags", [])]
        title_text = title.casefold()
        summary_text = summary.casefold()
        evidence_text = " ".join(
            [
                summary,
                str(payload.get("funding_evidence", "")),
                str(payload.get("funding_source", "") or ""),
                str(payload.get("funding_programme", "") or ""),
            ]
        ).casefold()
        source_title = source.title.casefold()
        generic_source_markers = (
            "projekty",
            "fundusze europejskie",
            "rewitalizacja",
            "podsumowanie",
            "aktualności",
            "news",
            "dofinansowaniami",
            "raport",
            "program",
        )
        generic_title_markers = (
            "strategia",
            "program ochrony środowiska",
            "gminny program rewitalizacji",
            "program rewitalizacji",
            "raport",
            "podsumowanie",
            "aktualności",
        )

        if len(title) < 8:
            return False
        if any(marker in title_text for marker in generic_title_markers):
            return False
        if not self._has_climate_relevance(f"{title_text} {summary_text}", climate_tags):
            return False
        if payload.get("funding_amount") is None and not self._has_funding_signal(evidence_text):
            return False
        if any(marker in source_title for marker in generic_source_markers) and SequenceMatcher(a=source_title, b=title_text).ratio() < 0.18:
            return False
        return True

    @staticmethod
    def _normalize_source_class(value: str, fallback: SourceClass) -> SourceClass:
        key = value.strip().casefold().replace("-", "_").replace(" ", "_")
        mapping = {
            "official": "city_root",
            "official_strong": "city_root",
            "official_source": "city_root",
            "high": "city_root",
            "municipal": "municipal_entity",
            "medium": "municipal_entity",
            "city_linked": "city_subdomain",
            "city_root": "city_root",
            "city_subdomain": "city_subdomain",
            "municipal_entity": "municipal_entity",
            "external": "supporting_external",
            "supporting": "supporting_external",
            "supporting_source": "supporting_external",
            "low": "reject_external",
            "weak": "reject_external",
            "reject_external": "reject_external",
        }
        normalized = mapping.get(key, key)
        if normalized in {"city_root", "city_subdomain", "municipal_entity", "supporting_external", "reject_external"}:
            return normalized  # type: ignore[return-value]
        return fallback

    @staticmethod
    def _has_inactive_signal(text: str, active: bool) -> bool:
        explicit_inactive = (
            "project completed",
            "works completed",
            "investment completed",
            "projekt zakończony",
            "zakończono realizację",
            "realizacja została zakończona",
            "ukończono",
            "oddano do użytku",
            "cancelled",
            "anulowano",
        )
        if any(token in text for token in explicit_inactive):
            return True
        if active:
            return False
        return any(token in text for token in config.INACTIVE_STATUS_HINTS)

    @staticmethod
    def _reject_non_project_page(source: ScrapedSource) -> str | None:
        title = source.title.casefold()
        lowered_url = source.url.casefold()
        path = urlparse(source.url).path.strip("/")
        if "#" in source.url:
            return "generic landing page rather than a single funded project"
        if any(
            marker in title
            for marker in ("spotkanie", "meeting", "conference", "workshop", "newsletter", "webinar", "seminar", "wizyta", "rozmowy", "badaniu", "weź udział")
        ):
            return "event/update page rather than a funded project record"
        if "study visit" in title:
            return "event/update page rather than a funded project record"
        if any(marker in title for marker in ("podsumowanie", "summary", "annual report", "year in review", "raport", "report on", "co dalej z", "archiwa", "strona 2 z", "strona 3 z")):
            return "summary/report page rather than a funded project record"
        if any(
            marker in lowered_url
            for marker in ("?team=", "/team/", "/category/", "/kategoria/", ",kategoria,", "/tag/", "/author/", "/page/2/", "/page/3/")
        ):
            return "profile or category page rather than a funded project record"
        if any(marker in title for marker in ("dr. ", "professor", "scientific projects", "information centre for foreigners", "living in szczecin")):
            return "profile or category page rather than a funded project record"
        if any(
            marker in title
            for marker in (
                "fundusze europejskie na infrastrukturę",
                "fundusze europejskie dla wielkopolski",
                "cztery nowe projekty",
                "projekty z dofinansowaniem",
                "projekty unijne",
                "miejskie centrum energii",
                "gminny program rewitalizacji",
                "program rewitalizacji",
                "plan adaptacji",
                "plan gospodarki niskoemisyjnej",
                "strategia rozwoju elektromobilności",
                "program ochrony środowiska",
            )
        ):
            return "generic funding-programme page rather than a single funded project"
        if any(
            marker in lowered_url
            for marker in (
                "siteassets/",
                "projekty-gpr-z-dofinansowaniem",
                "/rewitalizacja/rewitalizacja-w-lublinie",
                "/srodowisko-przyrodnicze-lublina/",
            )
        ):
            return "generic funding-programme page rather than a single funded project"
        if any(marker in title for marker in ("city development strategy", "eurocities", "c40", "sdg", "the katowice experience")):
            return "generic strategy or network page rather than a funded project record"
        if any(marker in title for marker in ("energy projects - ministry", "programme environment, energy and climate change")):
            return "generic national funding page rather than a funded project record"
        if source.source_kind == "pdf" and any(
            marker in f"{title} {lowered_url}"
            for marker in ("action plan", "plan_", "uchwala", "raport", "report", "program ochrony środowiska", "projekt_", "gms")
        ):
            return "summary/report page rather than a funded project record"
        if (not path or path.count("/") < 1) and any(
            marker in title for marker in ("unijne oblicze", "europejska warszawa", "fundusze europejskie", "projekty", "wiadomości", "aktualności")
        ):
            return "generic landing page rather than a single funded project"
        return None

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = re.sub(r"\s+", " ", title).strip(" -|")
        for marker in (" - Oficjalny serwis miejski", " | Oficjalny serwis miejski", " - Magiczny Kraków"):
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip(" -|")
        if " | " in cleaned:
            cleaned = cleaned.split(" | ", 1)[0].strip(" -|")
        return cleaned

    @staticmethod
    def _extract_funding_source(text: str) -> str | None:
        patterns = [
            r"(funded by [^.]+)",
            r"(co-financed by [^.]+)",
            r"(dofinansowan[yae] [^.]+)",
            r"(city budget[^.]+)",
            r"(budżetu miasta[^.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _extract_programme(text: str) -> str | None:
        patterns = [r"\bLIFE\b", r"\bFEnIKS\b", r"\bEU\b", r"\bEuropean Union\b", r"\bFundusz\b"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _extract_amount(text: str) -> float | None:
        match = re.search(r"(\d[\d\s.,]{2,})\s?(€|EUR|PLN|zł)", text)
        if not match:
            return None
        number = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return float(re.sub(r"[^0-9.]", "", number))
        except ValueError:
            return None

    @staticmethod
    def _extract_currency(text: str) -> str | None:
        match = re.search(r"(€|EUR|PLN|zł)", text)
        if not match:
            return None
        token = match.group(1)
        return {"€": "EUR", "zł": "PLN"}.get(token, token)

    @staticmethod
    def _extract_evidence(text: str, hints: tuple[str, ...]) -> str:
        lower = text.lower()
        for hint in hints:
            idx = lower.find(hint)
            if idx != -1:
                start = max(0, idx - 80)
                end = min(len(text), idx + 160)
                return text[start:end].strip()
        return ""

    @staticmethod
    def _extract_date(text: str) -> str | None:
        match = re.search(r"(20\d{2}-\d{2}-\d{2}|20\d{2}\.\d{2}\.\d{2}|20\d{2}/\d{2}/\d{2})", text)
        if match:
            return match.group(1).replace(".", "-").replace("/", "-")
        return None


def titles_are_similar(left: str, right: str) -> bool:
    return SequenceMatcher(a=left.casefold(), b=right.casefold()).ratio() >= 0.88
