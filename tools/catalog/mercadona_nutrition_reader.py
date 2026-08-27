from __future__ import annotations

from dataclasses import dataclass
from nutrition_label_reader import LabelReadResult, read_nutrition_label
from nutrition_resolver import NutritionCandidate, ProductIdentity
from mercadona_label_evidence import LabelImageEvidence

ADAPTER_VERSION = "1.0.2"
OCR_EVIDENCE_LEVEL = "OCR_DERIVED_FROM_MERCADONA_IMAGE"


@dataclass(frozen=True)
class VisionExtraction:
    text: str
    confidence: float
    engine: str
    engine_version: str | None = None


@dataclass(frozen=True)
class MercadonaLabelReading:
    evidence: LabelImageEvidence
    extraction: VisionExtraction
    parsed: LabelReadResult

    @property
    def accepted(self) -> bool:
        return self.parsed.declared_usable


def read_evidence(evidence: LabelImageEvidence, extraction: VisionExtraction) -> MercadonaLabelReading:
    """Interpret already-extracted text from one Mercadona pack image.

    The vision/OCR engine is intentionally injected. This module never assumes
    that an image is nutritional based on its position or filename.
    """
    parsed = read_nutrition_label(extraction.text, extraction_confidence=extraction.confidence)
    return MercadonaLabelReading(evidence, extraction, parsed)


def to_candidate(reading: MercadonaLabelReading, *, gtin: str | None = None,
                 brand: str | None = None, format: str | None = None) -> NutritionCandidate | None:
    """Convert a validated label reading into explicit OCR-derived build evidence.

    The source is a first-party Mercadona pack image, but its nutrition values
    are not structured text supplied by the retailer: they were recovered by
    OCR and then accepted by Rumbo's deterministic label parser. Keep that
    distinction in the evidence level all the way downstream.
    """
    if not reading.accepted or reading.parsed.nutrition is None:
        return None
    e = reading.evidence
    return NutritionCandidate(
        identity=ProductIdentity(
            name=e.product_name,
            brand=brand,
            gtin=gtin,
            format=format,
        ),
        nutrition=reading.parsed.nutrition,
        source="Mercadona label image OCR",
        source_url=e.image_url,
        source_record_id=f"{e.retailer_sku}:image:{e.image_index}",
        observed_at=e.observed_at,
        upstream_license=None,
        # Normalized values are kept separate from the source asset. False by
        # default until project publication policy explicitly clears them.
        redistribution_allowed=False,
        source_family="Mercadona label",
        claim=(f"{OCR_EVIDENCE_LEVEL}; reader={ADAPTER_VERSION}; "
               f"vision={reading.extraction.engine}:{reading.extraction.engine_version or 'unknown'}; "
               f"basis={reading.parsed.basis}"),
        evidence_level=OCR_EVIDENCE_LEVEL,
    )
