"""Sourced subject requirements — the qualitative rules, quoted from official sources.

These are the requirements that are *about the person and the scene* rather than about crop
geometry: expression, eyes, glasses, head coverings, background colour, recency, and whether
the image may be edited at all. They are checked against the SOURCE photo, before any effort
is spent cropping, because no crop can fix a smile or sunglasses.

Rules for this file:

* Every requirement carries a verbatim `quote` and the `source` URL it came from. If we cannot
  quote it, it does not go in.
* `check` says how — or whether — this project can assess it. Most of these cannot be assessed
  from pixels by any code we have. Saying so is the correct behaviour, not a gap to paper over.
* Nothing here is invented. Where a spec is silent, there is no entry, and the checker reports
  that the reviewed sources state no rule rather than importing one from another country.

Sources accessed 2026-09-04. See docs/PLAN.md for the full sourcing notes, including the
internal contradictions found within several of these documents.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

CN_SHEET = "https://bio.visaforchina.cn/KUL3_EN/upload/20231123/4b89d0c364d44f778f85d6fd76d93475.pdf"
US_VISA_PHOTOS = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html"
US_PASSPORT_PHOTOS = "https://travel.state.gov/en/passports/apply/help/photos.html"
EU_GUIDANCE = "https://home-affairs.ec.europa.eu/document/download/5bb16566-c8c2-4afb-b038-530f488cb72a_en"
NZ_PHOTOS = "https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/visa-and-nzeta-photos/"


class Check(enum.Enum):
    """How this project can assess a requirement."""

    ADVISORY_SIGNAL = "advisory_signal"
    """We have a model signal that is indicative but uncalibrated. Produces a warning with the
    score and threshold shown, never a verdict."""

    NOT_ASSESSABLE = "not_assessable"
    """No signal available in this build. Reported as not evaluated, never as a pass."""

    USER_ATTESTATION = "user_attestation"
    """Cannot be determined from pixels by anyone. The applicant must confirm it. Reported as
    an outstanding question, never silently assumed true."""

    OPERATION_POLICY = "operation_policy"
    """Constrains what this tool is permitted to DO to the photo, not what the photo shows."""


@dataclass(frozen=True)
class Requirement:
    key: str
    jurisdictions: tuple[str, ...]
    quote: str
    source: str
    check: Check
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "jurisdictions": list(self.jurisdictions),
            "quote": self.quote,
            "source": self.source,
            "check": self.check.value,
            "note": self.note,
        }


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        key="expression_neutral",
        jurisdictions=("CN",),
        quote=(
            "The facial expression must be neutral with eyes open, mouth closed."
        ),
        source=CN_SHEET,
        check=Check.ADVISORY_SIGNAL,
        note="Assessed with MediaPipe blendshapes against uncalibrated thresholds; see thresholds.py.",
    ),
    Requirement(
        key="expression_neutral_eu",
        jurisdictions=("EU",),
        quote="neutral expression, mouth closed",
        source=EU_GUIDANCE,
        check=Check.ADVISORY_SIGNAL,
    ),
    Requirement(
        key="eyes_open_eu",
        jurisdictions=("EU",),
        quote="eyes open and clearly visible",
        source=EU_GUIDANCE,
        check=Check.ADVISORY_SIGNAL,
    ),
    Requirement(
        key="glasses_cn",
        jurisdictions=("CN",),
        quote=(
            "Eyeglasses are allowed in the photo only if the lenses are not tinted and there "
            "is no glare, shadows, or frames obscuring the eyes."
        ),
        source=CN_SHEET,
        check=Check.NOT_ASSESSABLE,
        note="No tint, glare or frame-occlusion detector in this build.",
    ),
    Requirement(
        key="glasses_us_visa",
        jurisdictions=("US",),
        quote="Eyeglasses are no longer allowed in new visa photos",
        source=US_VISA_PHOTOS,
        check=Check.NOT_ASSESSABLE,
        note=(
            "In force since 2016-11-01, with a documented-medical-necessity exception. "
            "Stricter than CN/EU/NZ, which permit untinted prescription glasses."
        ),
    ),
    Requirement(
        key="glasses_nz",
        jurisdictions=("NZ",),
        quote=(
            "You can wear prescription glasses. Make sure your glasses: are clear and not "
            "tinted - no sunglasses; do not have heavy frames that cover your face, and do "
            "not create a glare or reflection in the photo."
        ),
        source=NZ_PHOTOS,
        check=Check.NOT_ASSESSABLE,
    ),
    Requirement(
        key="head_covering_cn",
        jurisdictions=("CN",),
        quote=(
            "Hats or other head coverings are only allowed if worn for religious reasons and "
            "if they do not obscure any facial features."
        ),
        source=CN_SHEET,
        check=Check.USER_ATTESTATION,
        note="Whether a covering is worn for religious reasons is not visible in the image.",
    ),
    Requirement(
        key="head_covering_nz",
        jurisdictions=("NZ",),
        quote=(
            "Remove any head coverings (unless worn for religious or medical reasons). If you "
            "wear a head covering for religious or medical reasons, your covering must not "
            "cover your mouth or the sides of your face."
        ),
        source=NZ_PHOTOS,
        check=Check.USER_ATTESTATION,
    ),
    Requirement(
        key="background_cn",
        jurisdictions=("CN",),
        quote=(
            "The background of the photo should be white or close to white with no borders "
            "around the edge of the image."
        ),
        source=CN_SHEET,
        check=Check.NOT_ASSESSABLE,
        note="Background uniformity scoring is deferred past v1; see ROADMAP.md (OFIQ).",
    ),
    Requirement(
        key="background_nz",
        jurisdictions=("NZ",),
        quote="plain, light-coloured (not white)",
        source=NZ_PHOTOS,
        check=Check.NOT_ASSESSABLE,
        note=(
            "NZ discourages white, where CN and US require white or off-white. There is no "
            "single background rule across jurisdictions."
        ),
    ),
    Requirement(
        key="recency_cn",
        jurisdictions=("CN",),
        quote="The photo should be recent, taken within 6 months.",
        source=CN_SHEET,
        check=Check.USER_ATTESTATION,
        note=(
            "Cannot be established from pixels. EXIF timestamps are trivially wrong or absent "
            "and are not evidence of when a face was photographed."
        ),
    ),
    Requirement(
        key="no_digital_alteration_nz",
        jurisdictions=("NZ",),
        quote=(
            "You cannot manipulate or digitally alter your photo using Artificial Intelligence "
            "(AI) or other digital editing tools."
        ),
        source=NZ_PHOTOS,
        check=Check.OPERATION_POLICY,
        note=(
            "Disables background replacement for NZ. INZ separately prohibits cutting out the "
            "head and shoulders and placing them on a plain background. Segmentation may still "
            "be used to MEASURE, so long as no altered pixels are emitted."
        ),
    ),
    Requirement(
        key="no_digital_alteration_us_passport",
        jurisdictions=("US",),
        quote="You may not digitally alter your photo",
        source=US_PASSPORT_PHOTOS,
        check=Check.OPERATION_POLICY,
        note="Applies to the US passport channel.",
    ),
)


# --- Generic advisories -------------------------------------------------------------------
# Used when the user has NOT told us what the photo is for. These are not invented: each is
# asserted, in substance, by a majority of the jurisdictions transcribed above, so they are a
# fair answer to "what commonly gets a formal photo rejected". They are still only advisories.
#
# A generic run must never claim conformance with anything. It says "these are the things that
# commonly cause rejection, and here is what we observed".

GENERIC_ADVISORIES: tuple[Requirement, ...] = (
    Requirement(
        key="generic_expression_neutral",
        jurisdictions=("GENERIC",),
        quote=(
            "A neutral expression with the mouth closed is required by CN and EU among the "
            "sources transcribed here."
        ),
        source=CN_SHEET,
        check=Check.ADVISORY_SIGNAL,
        note="Derived from the entries above, not from a single generic authority.",
    ),
    Requirement(
        key="generic_eyes_open",
        jurisdictions=("GENERIC",),
        quote="Eyes open and clearly visible is required by CN and EU among the sources transcribed here.",
        source=EU_GUIDANCE,
        check=Check.ADVISORY_SIGNAL,
        note="Derived. Sunglasses or closed eyes are a common cause of rejection everywhere.",
    ),
    Requirement(
        key="generic_no_tinted_lenses",
        jurisdictions=("GENERIC",),
        quote=(
            "Tinted lenses are prohibited by CN, EU and NZ; the US visa channel prohibits "
            "eyeglasses outright."
        ),
        source=NZ_PHOTOS,
        check=Check.NOT_ASSESSABLE,
        note="Derived. We have no tint or glare detector, so this is reported as not evaluated.",
    ),
    Requirement(
        key="generic_plain_background",
        jurisdictions=("GENERIC",),
        quote=(
            "A plain, uniform background is required by every source transcribed here, though "
            "they disagree on colour: CN and US require white or off-white, NZ requires "
            "light-coloured and not white."
        ),
        source=CN_SHEET,
        check=Check.NOT_ASSESSABLE,
        note="Derived. Background scoring is deferred past v1.",
    ),
    Requirement(
        key="generic_recency",
        jurisdictions=("GENERIC",),
        quote="A photo taken within the last 6 months is required by CN, US, EU and NZ.",
        source=CN_SHEET,
        check=Check.USER_ATTESTATION,
        note="Derived. All four transcribed sources agree on six months.",
    ),
    Requirement(
        key="generic_resolution",
        jurisdictions=("GENERIC",),
        quote=(
            "ICAO Portrait Quality Table 5 requires an inter-eye distance of at least 90 "
            "pixels and recommends at least 240."
        ),
        source="https://www.icao.int/sites/default/files/TRIP/Publications/TR-Portrait-Quality-v1.0.pdf",
        check=Check.ADVISORY_SIGNAL,
        note="The one generic advisory with a real numeric authority behind it.",
    ),
)


def for_jurisdiction(code: str) -> tuple[Requirement, ...]:
    """Requirements asserted by one jurisdiction. Empty is a meaningful answer: it means the
    reviewed sources for that jurisdiction state no subject requirement we transcribed, NOT
    that the jurisdiction has none."""
    return tuple(r for r in REQUIREMENTS if code.upper() in r.jurisdictions)


def jurisdictions() -> tuple[str, ...]:
    return tuple(sorted({j for r in REQUIREMENTS for j in r.jurisdictions}))
