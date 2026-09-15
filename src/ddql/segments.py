"""Segments and risk frameworks.

Risk scores are framework-conditional. A university donor check and a
corporate supplier check have different categories, different weights, and
different bands. Aggregate metrics across segments hide cohort regressions
(ADR-004).

Frameworks are versioned like rubrics. Changing a category weight is a version
bump.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ddql.types import Segment


@dataclass(frozen=True, slots=True)
class RiskCategory:
    id: str
    label: str
    weight: float
    question: str


@dataclass(frozen=True, slots=True)
class RiskFramework:
    id: str
    version: str
    segment: Segment
    categories: tuple[RiskCategory, ...]
    changelog: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def category(self, category_id: str) -> RiskCategory:
        for c in self.categories:
            if c.id == category_id:
                return c
        raise KeyError(f"{category_id} not in framework {self.ref}")


CORPORATE_SUPPLIER_V2 = RiskFramework(
    id="corporate_supplier",
    version="v2",
    segment=Segment.CORPORATE,
    categories=(
        RiskCategory("integrity", "Integrity", 0.20,
                     "Any adverse media, sanctions, or legal findings involving the entity or its principals?"),
        RiskCategory("esg", "ESG", 0.10,
                     "Environmental, social, or governance controversies with credible sourcing?"),
        RiskCategory("cybersecurity", "Cybersecurity", 0.15,
                     "Breach history, exposure on credential dumps, or security incidents?"),
        RiskCategory("financial", "Financial", 0.15,
                     "Insolvency, late filings, adverse credit events, or going-concern doubt?"),
        RiskCategory("geopolitical", "Geopolitical", 0.15,
                     "Operations or ownership in sanctioned or high-risk jurisdictions?"),
        RiskCategory("quality", "Quality", 0.10,
                     "Product recalls, regulatory quality findings, or customer complaints at scale?"),
        RiskCategory("business_continuity", "Business continuity", 0.15,
                     "Concentration risk, single-site dependency, or continuity threats?"),
    ),
    changelog=(
        "v2: cybersecurity weight 0.10 → 0.15 after Q1 incident review",
        "v2: added quality category at 0.10 (was folded into integrity in v1)",
        "v2: geopolitical merged with 'sanctions exposure' from v1",
    ),
)


LAW_FIRM_CLIENT_V1 = RiskFramework(
    id="law_firm_client",
    version="v1",
    segment=Segment.LAW_FIRM,
    categories=(
        RiskCategory("sanctions", "Sanctions", 0.20,
                     "On any sanctions list, directly or via ownership?"),
        RiskCategory("pep", "PEP", 0.15,
                     "Politically exposed person, or close associate/family of one?"),
        RiskCategory("adverse_media", "Adverse media", 0.20,
                     "Credible adverse coverage across jurisdictions?"),
        RiskCategory("source_of_wealth", "Source of wealth", 0.15,
                     "Is the stated source of wealth supported by the sources found?"),
        RiskCategory("aml_abc", "AML / ABC", 0.20,
                     "Money-laundering or anti-bribery exposure signals?"),
        RiskCategory("esg", "ESG", 0.10,
                     "Environmental, social, or governance red flags?"),
    ),
    changelog=("v1: initial, aligned to standard client-onboarding framework",),
)


PRIVATE_BANK_HNW_V1 = RiskFramework(
    id="private_bank_hnw",
    version="v1",
    segment=Segment.PRIVATE_BANK,
    categories=(
        RiskCategory("background", "Background", 0.15,
                     "Education, early career, and public biographical record consistent?"),
        RiskCategory("career", "Career", 0.15,
                     "Professional history supports the client's stated profile?"),
        RiskCategory("business_associations", "Business associations", 0.15,
                     "Directorships, shareholdings, and partnerships disclosed and grounded?"),
        RiskCategory("philanthropy", "Philanthropy", 0.10,
                     "Philanthropic activity supports the stated source of wealth?"),
        RiskCategory("source_of_wealth", "Source of wealth", 0.20,
                     "Is the stated source of wealth independently supported?"),
        RiskCategory("sanctions", "Sanctions", 0.15,
                     "On any sanctions list, directly or via ownership?"),
        RiskCategory("pep", "PEP", 0.10,
                     "PEP status, or close associate/family of one?"),
    ),
    changelog=("v1: initial, aligned to private-bank onboarding framework",),
)


UNIVERSITY_DONOR_V1 = RiskFramework(
    id="university_donor",
    version="v1",
    segment=Segment.UNIVERSITY,
    categories=(
        RiskCategory("reputational", "Reputational", 0.25,
                     "Would accepting this gift attract credible public criticism?"),
        RiskCategory("sanctions", "Sanctions", 0.20,
                     "Donor or their entities on any sanctions list?"),
        RiskCategory("gift_acceptance_policy", "Gift acceptance policy", 0.20,
                     "Does the gift conflict with the institution's stated policy?"),
        RiskCategory("source_of_wealth", "Source of wealth", 0.20,
                     "Is the source of the gift independently supported?"),
        RiskCategory("research_integrity", "Research integrity", 0.15,
                     "Any research-misconduct or academic-integrity findings?"),
    ),
    changelog=("v1: initial, aligned to sector gift-acceptance guidance",),
)


NONPROFIT_DONOR_V1 = RiskFramework(
    id="nonprofit_donor",
    version="v1",
    segment=Segment.NONPROFIT,
    categories=(
        RiskCategory("reputational", "Reputational", 0.30,
                     "Would accepting this gift attract credible public criticism?"),
        RiskCategory("sanctions", "Sanctions", 0.20,
                     "Donor or their entities on any sanctions list?"),
        RiskCategory("gift_acceptance_policy", "Gift acceptance policy", 0.20,
                     "Does the gift conflict with the charity's stated policy?"),
        RiskCategory("source_of_wealth", "Source of wealth", 0.30,
                     "Is the source of the gift independently supported?"),
    ),
    changelog=("v1: initial, aligned to charitable-sector guidance",),
)


FRAMEWORKS: dict[str, RiskFramework] = {
    f.id: f for f in (
        CORPORATE_SUPPLIER_V2,
        LAW_FIRM_CLIENT_V1,
        PRIVATE_BANK_HNW_V1,
        UNIVERSITY_DONOR_V1,
        NONPROFIT_DONOR_V1,
    )
}


def for_segment(segment: Segment) -> RiskFramework:
    for f in FRAMEWORKS.values():
        if f.segment == segment:
            return f
    raise KeyError(f"no default framework for segment {segment}")


def by_ref(ref: str) -> RiskFramework:
    """Look up by 'id@version' or just 'id'."""
    base = ref.split("@", 1)[0]
    if base not in FRAMEWORKS:
        raise KeyError(f"unknown framework {ref}")
    return FRAMEWORKS[base]