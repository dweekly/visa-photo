"""Destination profiles: a channel's published geometry, and how to turn it into constraints.

A profile describes **one submission channel** of one destination. Channels do not inherit
from one another, and nothing inherits from ICAO. China's paper photo and its digital photo
are two profiles with different aspect ratios and different rules; applying one channel's
millimetre bands to the other is the mistake this whole project exists to prevent.

Every numeric bound carries the verbatim text it came from. If a source is silent, there is
no rule here, and the solver is given no constraint - the absence is reported rather than
filled in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .geometry import Constraint
from .measurements import MeasurementSet

CN_SHEET = (
    "https://bio.visaforchina.cn/KUL3_EN/upload/20231123/"
    "4b89d0c364d44f778f85d6fd76d93475.pdf"
)


@dataclass(frozen=True)
class Rule:
    """One geometric bound, with the words it came from."""

    key: str
    quote: str
    measurement: str
    """Which Stage 1 measurement this rule is expressed against. If that measurement is
    unavailable, the rule cannot be applied and the report says so."""

    lo: float | None = None
    hi: float | None = None
    lo_strict: bool = False
    """True when the source says "greater than", not "at least": a value equal to `lo` fails."""
    hi_strict: bool = False
    unit: str = "px"
    """`px` (stated at the reference size), `mm` (a print), or `fraction_height` (a fraction
    of the output image's height, as the US states its digital rules)."""
    note: str = ""
    interpretation: str = ""
    """The reading applied when the quote is not a computable definition ("face covers 70-80%
    of the image"). Printed wherever the rule appears; empty when the quote defines the
    quantity itself."""
    derivation: str = ""
    """Arithmetic the quote implies but does not state as the bound used ("205 +/- 14 ->
    191-219"). Not an interpretation: no reading was chosen, only a sum done."""
    source: str = ""
    """URL of the page the quote is from; inherits the profile's when empty."""
    retrieved: str = ""
    """Retrieval date of that page; inherits the profile's when empty."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "quote": self.quote, "measurement": self.measurement,
            "lo": self.lo, "hi": self.hi, "lo_strict": self.lo_strict, "hi_strict": self.hi_strict,
            "unit": self.unit, "note": self.note, "interpretation": self.interpretation,
            "derivation": self.derivation, "source": self.source, "retrieved": self.retrieved,
        }


@dataclass(frozen=True)
class OutputSize:
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass(frozen=True)
class DimensionRange:
    """Permitted dimensions stated as a range with a fixed aspect, as the US ("600 x 600
    minimum, 1200 x 1200 maximum, square") and New Zealand ("between 900 x 1200 and 2250 x 3000
    pixels", 3:4) state them. `aspect` is exact and integer: (1, 1), (3, 4)."""

    min: OutputSize
    max: OutputSize
    aspect: tuple[int, int]
    quote: str = ""
    source: str = ""

    def permits(self, width: int, height: int) -> tuple[bool, str]:
        aw, ah = self.aspect
        if width * ah != height * aw:
            return False, f"{width}x{height} is not {aw}:{ah}"
        if not (self.min.width <= width <= self.max.width and self.min.height <= height <= self.max.height):
            return False, (f"{width}x{height} is outside {self.min.width}x{self.min.height} to "
                           f"{self.max.width}x{self.max.height}")
        return True, f"{width}x{height} is {aw}:{ah} and within the permitted range"

    def to_dict(self) -> dict[str, Any]:
        return {"min": {"width": self.min.width, "height": self.min.height},
                "max": {"width": self.max.width, "height": self.max.height},
                "aspect": list(self.aspect), "quote": self.quote, "source": self.source}


@dataclass(frozen=True)
class SizeReading:
    """One reading of a published file-size band. "40 KB - 120 KB" has two: a kilobyte of 1,000
    bytes and one of 1,024. A validator reports each; the encoder targets their intersection."""

    name: str
    min_bytes: int | None
    max_bytes: int | None

    def contains(self, size: int) -> bool:
        return ((self.min_bytes is None or size >= self.min_bytes)
                and (self.max_bytes is None or size <= self.max_bytes))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "min_bytes": self.min_bytes, "max_bytes": self.max_bytes}


@dataclass(frozen=True)
class Encoding:
    """A channel's published file rules, as quoted, beside this tool's reading of them.

    `quote` is the source's wording. `size_readings` are the readings of its size band;
    `min_bytes` / `max_bytes` are their intersection, which is what the encoder targets so a
    file inside it satisfies every reading. `colour` and `subsampling` are the encoder's
    choices, and `interpretation` says which is which. Absent on a print profile.
    """

    format: str
    """`jpeg` is the only format this build writes."""
    colour: str
    """What the encoder writes: `srgb_24bit`, 8 bits per channel RGB, sRGB primaries, no
    embedded profile. The encoder's choice, fixed, and not by itself a requirement."""
    quote: str
    interpretation: str
    size_readings: tuple[SizeReading, ...] = ()
    subsampling: str = "4:4:4"
    colour_required: str | None = None
    """What the source requires of the file, if it says: `rgb_24bit` ("RGB 24bit true colour")
    or `srgb_24bit` ("24 bits per pixel in sRGB color space"). None when the source states no
    colour requirement; the validator then checks nothing about colour."""
    max_compression_ratio: float | None = None
    """A cap on compression ratio is a floor on bytes. Read as uncompressed bytes = width x
    height x 3 (8-bit RGB) over the written file's bytes, headers included; the reading is in
    `compression_reading`."""
    compression_reading: str = ""
    source: str = ""

    def min_bytes_for(self, width: int, height: int) -> int | None:
        """The floor at one output size: the readings' intersection and the compression floor,
        whichever is higher."""
        floors = [self.min_bytes]
        if self.max_compression_ratio is not None:
            floors.append(int(-(-width * height * 3 // self.max_compression_ratio)))  # ceil
        floors = [f for f in floors if f is not None]
        return max(floors) if floors else None

    @property
    def min_bytes(self) -> int | None:
        mins = [r.min_bytes for r in self.size_readings if r.min_bytes is not None]
        return max(mins) if mins else None

    @property
    def max_bytes(self) -> int | None:
        maxes = [r.max_bytes for r in self.size_readings if r.max_bytes is not None]
        return min(maxes) if maxes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format, "colour": self.colour,
            "size_readings": [r.to_dict() for r in self.size_readings],
            "min_bytes": self.min_bytes, "max_bytes": self.max_bytes,
            "subsampling": self.subsampling, "quote": self.quote,
            "interpretation": self.interpretation, "colour_required": self.colour_required,
            "max_compression_ratio": self.max_compression_ratio,
            "compression_reading": self.compression_reading, "source": self.source,
        }


@dataclass(frozen=True)
class Profile:
    key: str
    destination: str
    channel: str
    source: str
    retrieved: str
    jurisdiction: str
    """The requirements.py jurisdiction code whose advisories apply alongside these rules."""
    sizes: tuple[OutputSize, ...]
    rules: tuple[Rule, ...]
    sizes_quote: str = ""
    """The source's wording for the permitted dimensions."""
    physical_mm: tuple[float, float] | None = None
    """Printed size, when the rules are stated in millimetres. Bounds in mm are converted to
    output pixels through this and the output size before any constraint is built - a pixel
    measurement compared against a millimetre bound rejects every photograph."""

    reference_size: OutputSize | None = None
    """The size at which pixel-denominated rules were stated. China gives its pixel figures
    "as an example" at 354x472 and never says whether they scale. We therefore apply them
    literally and only at sizes we can justify - see `sizes_for_pixel_rules`."""

    operations: dict[str, str] = field(default_factory=dict)
    operations_quotes: dict[str, str] = field(default_factory=dict)
    """The sentence each operation policy rests on, per channel, keyed by operation."""
    encoding: Encoding | None = None
    """The channel's file rules for a digital upload; None for a print profile."""
    dimensions: DimensionRange | None = None
    """Permitted dimensions as a range, when the source states one; None means exactly the
    listed `sizes`. `sizes` stays the ordered list the solver tries."""
    composition_unresolved: str = ""
    """When the reviewed sources state no computable composition rule, the reason. The plan
    skips every size with it: no crop is solved from rules nobody wrote."""
    notes: tuple[str, ...] = ()

    def provenance(self, rule: Rule) -> tuple[str, str]:
        """(source URL, retrieval date) for a rule, inheriting the profile's when unset."""
        return (rule.source or self.source, rule.retrieved or self.retrieved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "destination": self.destination, "channel": self.channel,
            "source": self.source, "retrieved": self.retrieved,
            "jurisdiction": self.jurisdiction,
            "sizes": [{"width": s.width, "height": s.height} for s in self.sizes],
            "sizes_quote": self.sizes_quote,
            "reference_size": (
                {"width": self.reference_size.width, "height": self.reference_size.height}
                if self.reference_size else None
            ),
            "rules": [r.to_dict() for r in self.rules],
            "operations": self.operations,
            "operations_quotes": self.operations_quotes,
            "encoding": self.encoding.to_dict() if self.encoding else None,
            "dimensions": self.dimensions.to_dict() if self.dimensions else None,
            "composition_unresolved": self.composition_unresolved or None,
            "notes": list(self.notes),
        }


# --- China, online application (digital) --------------------------------------------------
# NOTE what is NOT here: this channel states no head-height bound and no chin-to-bottom-edge
# bound. Both exist only in the paper profile, in millimetres. Their absence is the point.
CN_VISA_DIGITAL = Profile(
    key="cn_visa_digital",
    jurisdiction="CN",
    destination="China",
    channel="online visa application (digital photo)",
    source=CN_SHEET,
    retrieved="2026-09-04",
    sizes=(OutputSize(354, 472), OutputSize(420, 560)),
    sizes_quote="The digital photo should be between 354 pixels (width) x 472 pixels (height) "
                "and 420 pixels (width) x 560 pixels (height).",
    reference_size=OutputSize(354, 472),
    rules=(
        Rule(
            key="face_width",
            quote=(
                "With the digital photo of 354 pixels (width) x 472 pixels (height) as an "
                "example, the head should be horizontally centered in the image with the "
                "face width at 205 pixels +/- 14 pixels."
            ),
            measurement="head_width_silhouette",
            lo=191.0, hi=219.0,
            derivation="205 - 14 = 191, 205 + 14 = 219",
            note=(
                "Stated at the 354x472 reference size. The sheet's own diagram gives a wider "
                "191-251 px instead; both readings are recorded in PLAN.md. This profile uses "
                "the body text."
            ),
        ),
        Rule(
            key="crown_gap",
            quote=(
                "The space from the upper edge of the image to the crown of the head should "
                "be 10 - 70 pixels."
            ),
            measurement="matte_top_row",
            lo=10.0, hi=70.0,
            note="The diagram on the same sheet says 10-85 px. Body text used.",
        ),
        Rule(
            key="eye_line_from_bottom",
            quote=(
                "The vertical distance from the bottom edge of the image to the horizontal "
                "line through the centre of the eyes should be > 256 pixels."
            ),
            measurement="eye_line_y",
            lo=256.0, lo_strict=True,
            note="The text says > 256; the diagram is labelled \u2265 256. The text's reading, the "
                 "stricter, is applied; a value of exactly 256 fails.",
        ),
        Rule(
            key="inter_eye_distance",
            quote="The inter-eye distance should be > 60 pixels.",
            measurement="inter_eye_distance",
            lo=60.0, lo_strict=True,
        ),
    ),
    operations={
        "crop": "allowed", "resize": "allowed", "encode": "allowed",
        "rotate": "unresolved", "replace_background": "unresolved",
        "adjust_colour": "unresolved", "synthesize_pixels": "prohibited",
    },
    encoding=Encoding(
        format="jpeg", colour="srgb_24bit", colour_required="rgb_24bit",
        quote="Colour Space: RGB 24bit true colour. Image Compression: JPEG and the image "
              "file size: 40 KB - 120 KB.",
        interpretation="The sheet does not say which kilobyte it means, so both readings are "
                       "kept: the encoder targets their intersection (40,960-120,000 bytes) "
                       "and the validator reports each. The sheet states 24-bit RGB; sRGB as "
                       "the RGB space, and 4:4:4 chroma, are this tool's choices.",
        size_readings=(
            SizeReading("KB = 1,000 bytes", 40_000, 120_000),
            SizeReading("KB = 1,024 bytes", 40_960, 122_880),
        ),
    ),
    notes=(
        "This channel states NO head-height bound. Do not import one from the paper profile.",
        "MFA allows up to 420x560; the CVASC upload FAQ says photos cannot exceed 354x472.",
    ),
)


CN_VISA_PAPER = Profile(
    key="cn_visa_paper",
    jurisdiction="CN",
    destination="China",
    channel="paper photo for the visa application form",
    source=CN_SHEET,
    retrieved="2026-09-04",
    sizes=(OutputSize(390, 567),),  # 33x48 mm at 300 dpi
    physical_mm=(33.0, 48.0),
    rules=(
        Rule(
            key="head_height",
            quote=(
                "the head height, measured from the base of the chin to the crown of the "
                "head, should be between 28 mm and 33 mm."
            ),
            measurement="head_height",
            lo=28.0, hi=33.0, unit="mm",
        ),
        Rule(
            key="head_width",
            quote="The head width should be between 15 mm and 22 mm",
            measurement="head_width_silhouette",
            lo=15.0, hi=22.0, unit="mm",
        ),
        Rule(
            key="crown_gap",
            quote=(
                "The space between the crown and the upper edge of the photo should be "
                "between 3 mm and 5 mm."
            ),
            measurement="matte_top_row",
            lo=3.0, hi=5.0, unit="mm",
        ),
        Rule(
            key="chin_to_bottom",
            quote=(
                "The space between the chin and the bottom edge of the photo should be "
                ">= 7 mm."
            ),
            measurement="chin_landmark_y",
            lo=7.0, unit="mm",
        ),
    ),
    operations={"crop": "allowed", "resize": "allowed", "encode": "allowed"},
    notes=("Millimetre bands. This is a different aspect ratio from the digital channel "
           "(33:48 against 354:472), so the two are not convertible.",),
)


# --- United States ---------------------------------------------------------------------------
# Sources fetched 2026-09-06, verbatim in docs/sources/us-state-department-2026-09-06.md. Two
# channels with different rules: the visa photo (DS-160 digital image) and the printed passport
# photo. The visa page's "22 mm" beside "1 inch" is arithmetically inconsistent (1 in = 25.4 mm)
# and contradicts the FAQ and the passport page, which say 25; recorded, not applied.
US_VISA_PHOTOS = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html"
US_VISA_FAQ = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/frequently-asked-questions.html"
US_DIGITAL = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/digital-image-requirements.html"
US_TEMPLATE = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/photo-composition-template.html"
US_PASSPORT = "https://travel.state.gov/en/passports/apply/help/photos.html"

US_VISA_DIGITAL = Profile(
    key="us_visa_digital",
    jurisdiction="US",
    destination="United States",
    channel="visa application (DS-160), digital image",
    source=US_VISA_PHOTOS,
    retrieved="2026-09-06",
    sizes=(OutputSize(600, 600), OutputSize(1200, 1200)),
    sizes_quote="Minimum acceptable dimensions are 600 x 600 pixels. Maximum acceptable "
                "dimensions are 1200 x 1200 pixels.",
    dimensions=DimensionRange(
        min=OutputSize(600, 600), max=OutputSize(1200, 1200), aspect=(1, 1),
        quote="The image dimensions must be in a square aspect ratio (the height must be equal "
              "to the width). Minimum acceptable dimensions are 600 x 600 pixels. Maximum "
              "acceptable dimensions are 1200 x 1200 pixels.",
        source=US_DIGITAL,
    ),
    rules=(
        Rule(
            key="head_height",
            quote="Sized such that the head is between 1 inch and 1 3/8 inches (22 mm and 35 mm) "
                  "or 50% and 69% of the image's total height from the bottom of the chin to the "
                  "top of the head.",
            measurement="head_height",
            lo=0.50, hi=0.69, unit="fraction_height",
            derivation="50% and 69% of the image's total height",
            note="The FAQ defines the span as 'from the top of the head, including the hair, to "
                 "the bottom of the chin'; the matte's top row is that quantity. The page's "
                 "'22 mm' is not applied: 1 inch is 25.4 mm, and the FAQ and the passport page "
                 "both say 25.",
        ),
        Rule(
            key="eye_line_from_bottom",
            quote="600 px. \u00b7 600 px. \u00b7 50-69% \u00b7 56-69%",
            measurement="eye_line_y",
            lo=0.56, hi=0.69, unit="fraction_height",
            source=US_TEMPLATE,
            derivation="56-69% of the image height, from the bottom edge to the eye line",
            note="A graphic label, not prose: the composition-template page has no body text, "
                 "and the '56-69%' dimension line on the 'Digital Image Head Size Template' "
                 "runs from the bottom edge to the eye line. No sentence on any page read "
                 "states an eye-height rule.",
        ),
    ),
    operations={
        "crop": "allowed", "resize": "allowed", "encode": "allowed", "colour_convert": "allowed",
        "rotate": "unresolved", "replace_background": "prohibited",
        "adjust_colour": "prohibited", "synthesize_pixels": "prohibited",
    },
    operations_quotes={
        "crop": "crop it to a square image of exactly 600 x 600 pixels",
        "resize": "The image dimensions must be in a square aspect ratio ... Minimum acceptable "
                  "dimensions are 600 x 600 pixels.",
        "encode": "The image must be in JPEG file format",
        "colour_convert": "The image must be in color (24 bits per pixel) in sRGB color space",
        "replace_background": "Photos must not be digitally enhanced or altered to change your "
                              "appearance in any way.",
        "adjust_colour": "Photos must not be digitally enhanced or altered to change your "
                         "appearance in any way.",
        "synthesize_pixels": "Photos must not be digitally enhanced or altered to change your "
                             "appearance in any way.",
    },
    encoding=Encoding(
        format="jpeg", colour="srgb_24bit", colour_required="srgb_24bit",
        quote="The image must be in color (24 bits per pixel) in sRGB color space which is the "
              "common output for most digital cameras. The image must be in JPEG file format. "
              "The image must be less than or equal to 240 kB (kilobytes). The compression ratio "
              "should be less than or equal to 20:1.",
        interpretation="'240 kB' is kept under both readings of kB. The compression cap is read "
                       "as a floor on bytes: width x height x 3 (8-bit RGB) over 20, the written "
                       "file's bytes counted with their headers. 4:4:4 chroma is this tool's "
                       "choice; sRGB and 24 bits are the source's.",
        size_readings=(
            SizeReading("kB = 1,000 bytes", None, 240_000),
            SizeReading("kB = 1,024 bytes", None, 245_760),
        ),
        max_compression_ratio=20.0,
        compression_reading="uncompressed bytes = width x height x 3; the file, headers included, "
                            "must be at least one twentieth of that",
        source=US_DIGITAL,
    ),
    notes=(
        "The visa page says '1 inch and 1 3/8 inches (22 mm and 35 mm)'; the FAQ and the passport "
        "page say 25-35 mm, and 1 inch is 25.4 mm. The fraction rule is applied; the millimetre "
        "figures are not.",
        "The eye-line band exists only as a label on the composition-template graphic.",
        "Eyeglasses are not allowed in visa photos (see the advisories).",
        "The Department's own photo tool crops to 'exactly 600 x 600 pixels', so 600x600 is tried "
        "first; 1200x1200 second.",
        "At 1200x1200 the 20:1 cap leaves a band of 216,000-240,000 bytes; the encoder searches "
        "every integer quality from 98 down for one inside it, and reports if none is.",
    ),
)

US_PASSPORT_PRINT = Profile(
    key="us_passport_print",
    jurisdiction="US",
    destination="United States",
    channel="passport, printed photo",
    source=US_PASSPORT,
    retrieved="2026-09-06",
    sizes=(OutputSize(600, 600),),  # 2 x 2 in at 300 ppi
    sizes_quote="The correct printed size of a passport photo is 2 x 2 inches (51 x 51 mm).",
    physical_mm=(50.8, 50.8),
    rules=(
        Rule(
            key="head_height",
            quote="The size of your head in the printed photo must be between 1 -1 3/8 inches "
                  "(25 - 35 mm) from the bottom of the chin to the top of the head.",
            measurement="head_height",
            lo=25.0, hi=35.0, unit="mm",
            interpretation="The passport page does not say whether 'the top of the head' "
                           "includes hair, and allows hair past the frame; the hair-inclusive "
                           "matte top is used, as the visa FAQ defines the same span.",
            note="The page's own tips say 'between 1 inch and 1.4 inches (25 and 35 mm)'; "
                 "1 3/8 in is 34.9 mm and 1.4 in is 35.6 mm. The stated 25-35 mm is applied.",
        ),
        Rule(
            key="eye_line_from_bottom",
            quote="2 inch \u00b7 2 inch \u00b7 1 inch to 1 3/8 inch \u00b7 1 1/8 inch to 1 3/8 inch",
            measurement="eye_line_y",
            lo=28.575, hi=34.925, unit="mm",
            source=US_TEMPLATE,
            derivation="1 1/8 in x 25.4 = 28.575 mm; 1 3/8 in x 25.4 = 34.925 mm",
            interpretation="Taken from the visa-side 'Paper Photo Head Size Template' graphic; "
                           "the passport pages state no eye-height rule and the passport-side "
                           "template page does not exist.",
            note="A graphic label, not prose.",
        ),
    ),
    operations={
        "crop": "allowed", "resize": "unresolved", "encode": "allowed",
        "rotate": "unresolved", "replace_background": "prohibited",
        "adjust_colour": "prohibited", "synthesize_pixels": "prohibited",
    },
    operations_quotes={
        "crop": "Your hair may extend past the edges of the photo, as long as your entire head is "
                "shown and is the appropriate size.",
        "resize": "Do not stretch or compress your image to resize it.",
        "replace_background": "Submit the original, unchanged photo. Do not change your photo "
                              "using computer software, phone apps or filters, or artificial "
                              "intelligence.",
        "adjust_colour": "Do not change your photo using computer software, phone apps or "
                         "filters, or artificial intelligence.",
        "synthesize_pixels": "Do not change your photo using computer software, phone apps or "
                             "filters, or artificial intelligence.",
    },
    notes=(
        "2 inches governs (50.8 mm); the page's '51 x 51 mm' is its rounding.",
        "'Do not stretch or compress your image to resize it' - uniform scaling to the printed "
        "size is read as neither, and left unresolved rather than asserted.",
        "Print output is not produced by this build; this profile plans only.",
    ),
)

# --- New Zealand -----------------------------------------------------------------------------
# Sources fetched 2026-09-06, verbatim in docs/sources/nz-immigration-2026-09-06.md. One page
# governs visas and the NZeTA alike; the upload-error page and the photographer sheet state the
# pixel range in text and a different byte band.
NZ_PHOTOS = "https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/visa-and-nzeta-photos/"
NZ_ERRORS = "https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/fixing-errors-when-uploading-a-photo/"
NZ_PHOTOGRAPHER = "https://www.immigration.govt.nz/assets/inz/documents/apply-for-a-visa/Taking-acceptable-visa-photos.pdf"

NZ_NZETA = Profile(
    key="nz_nzeta",
    jurisdiction="NZ",
    destination="New Zealand",
    channel="NZeTA and online visa application, digital photo",
    source=NZ_PHOTOS,
    retrieved="2026-09-06",
    sizes=(OutputSize(2250, 3000), OutputSize(1500, 2000), OutputSize(900, 1200)),
    sizes_quote="between 900 x 1200 and 2250 x 3000 pixels",
    dimensions=DimensionRange(
        min=OutputSize(900, 1200), max=OutputSize(2250, 3000), aspect=(3, 4),
        quote="Your photo must be: between 900 x 1200 and 2250 x 3000 pixels; between 500 KB "
              "and 3 MB, and; in portrait format.",
        source=NZ_ERRORS,
    ),
    rules=(
        Rule(
            key="head_height",
            quote="your face covers between 70% and 80% of the image and is in the middle of "
                  "the frame",
            measurement="head_height",
            lo=0.70, hi=0.80, unit="fraction_height",
            interpretation="'face covers between 70% and 80% of the image' read as hair-inclusive "
                           "head height (matte top to chin) over image height; INZ's photographer "
                           "sheet says 'the length of the head fills 75% of the frame'.",
            note="The applicant page defines neither 'face' nor 'of the image'. The photographer "
                 "sheet gives fixed figures instead of a band (head length 75%, head width 70%).",
        ),
    ),
    operations={
        "crop": "allowed", "resize": "allowed", "encode": "allowed", "colour_convert": "allowed",
        "rotate": "unresolved", "replace_background": "prohibited",
        "adjust_colour": "prohibited", "synthesize_pixels": "prohibited",
    },
    operations_quotes={
        "crop": "Your photo must be: between 512 KB and 3.14 MB; taken in portrait mode with 3:4 "
                "aspect ratio; a JPG or JPEG file.",
        "resize": "Your photo must be: between 900 x 1200 and 2250 x 3000 pixels",
        "encode": "a JPG or JPEG file",
        "colour_convert": "set the colour to sRGB (to match the colours that most video monitors "
                          "and printers reproduce)",
        "replace_background": "cropping your head and shoulders to place it on a plain background",
        "adjust_colour": "changing the colour, brightness, contrast or sharpness",
        "synthesize_pixels": "digitally removing objects from the photo, especially around the "
                             "image of your face",
    },
    encoding=Encoding(
        format="jpeg", colour="srgb_24bit", colour_required=None,
        quote="Your photo must be: between 512 KB and 3.14 MB; taken in portrait mode with 3:4 "
              "aspect ratio; a JPG or JPEG file.",
        interpretation="Two INZ pages give different bands - 512 KB to 3.14 MB on the requirements "
                       "page, 500 KB to 3 MB on the upload-error page and the photographer sheet - "
                       "and neither says which kilobyte it means. All four readings are kept: the "
                       "encoder targets their intersection, the validator reports each. The "
                       "applicant page states no colour requirement; sRGB is this tool's choice "
                       "(the photographer sheet instructs 'set the colour to sRGB').",
        size_readings=(
            SizeReading("requirements page, KB = 1,000 bytes", 512_000, 3_140_000),
            SizeReading("requirements page, KB = 1,024 bytes", 524_288, 3_292_528),
            SizeReading("upload-error page, KB = 1,000 bytes", 500_000, 3_000_000),
            SizeReading("upload-error page, KB = 1,024 bytes", 512_000, 3_145_728),
        ),
        source=NZ_PHOTOS,
    ),
    notes=(
        "File size: the requirements page says 512 KB-3.14 MB; the upload-error page and the "
        "photographer sheet say 500 KB-3 MB. Both are live.",
        "The pixel range appears on the requirements page only inside an image; the upload-error "
        "page and the photographer sheet state it in text.",
        "Background: the requirements page says 'neutral and plain'; the error page suggests "
        "'light grey'; the photographer sheet requires 'plain, light-coloured (not white)'.",
        "Largest size first: the byte floor is easier to reach with more pixels.",
    ),
)

# --- Schengen ----------------------------------------------------------------------------------
# Sources fetched 2026-09-06, verbatim in docs/sources/schengen-icao-2026-09-06.md. No EU-level
# source states a computable composition rule, and the ICAO rule the sources reach governs the
# printed portrait inside the finished document. This profile plans nothing; it records what is
# stated and advises.
EU_GUIDANCE = "https://home-affairs.ec.europa.eu/document/download/5bb16566-c8c2-4afb-b038-530f488cb72a_en?filename=icao_photograph_guidelines_en.pdf"
EU_VISA_CODE = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02009R0810-20200202"
ICAO_9303_P3 = "https://www.icao.int/sites/default/files/publications/DocSeries/9303_p3_cons_en.pdf"

SCHENGEN_PRINT = Profile(
    key="schengen_print",
    jurisdiction="EU",
    destination="Schengen area",
    channel="visa application, printed photo",
    source=EU_GUIDANCE,
    retrieved="2026-09-06",
    sizes=(OutputSize(413, 531),),  # 35 x 45 mm at 300 dpi
    sizes_quote="Submitted portraits should be 45.0 mm x 35.0 mm (1.77 in x 1.38 in) in dimension.",
    physical_mm=(35.0, 45.0),
    rules=(),
    composition_unresolved=(
        "no computable composition rule: the Visa Code binds photographs to 'ICAO document 9303 "
        "Part 1, 6th edition'; the only numeric head rule any reviewed source states is Doc 9303 "
        "Part 3, eighth edition, 3.9.1.3, which measures the crown-to-chin portion of the printed "
        "portrait 'of the longest dimension defined for Zone V' of the finished document, not the "
        "submitted photograph, and defines the crown as 'the top of the head ignoring any hair'; "
        "the EU sheet's 'face takes up 70-80% of the photograph' defines nothing"
    ),
    operations={"crop": "unresolved", "resize": "unresolved", "encode": "unresolved",
                "rotate": "unresolved", "replace_background": "unresolved",
                "adjust_colour": "unresolved", "synthesize_pixels": "unresolved"},
    notes=(
        "The EU sheet states, in full: 'no more than 6-months old'; '35-40mm in width'; 'close "
        "up of your head and top of your shoulders so that your face takes up 70-80% of the "
        "photograph'. Its PDF metadata is a 2003 QuarkXPress brochure; no Commission page links "
        "it.",
        "The 45.0 x 35.0 mm size is ICAO Doc 9303 Part 3 (eighth edition) 3.9.1.2, not an EU "
        "instrument; the EU sheet gives only a width range.",
        "France: 'La taille du visage doit \u00eatre de 32 \u00e0 36 mm ... du bas du menton au sommet "
        "du cr\u00e2ne (hors chevelure)'; its English FAQ says 'from chin to forehead (excluding "
        "hair)'. Germany: 'Das Gesicht nimmt 70 bis 80 % der H\u00f6he des Fotos ein' from 'der "
        "Kinnspitze bis zum oberen Kopfende'. Both hair-exclusive or ambiguous about hair; neither "
        "applied here (ROADMAP: member-state overlays).",
        "Print output is not produced by this build.",
    ),
)

PROFILES: dict[str, Profile] = {
    p.key: p for p in (CN_VISA_DIGITAL, CN_VISA_PAPER, US_VISA_DIGITAL, US_PASSPORT_PRINT,
                       NZ_NZETA, SCHENGEN_PRINT)
}


class ProfileError(RuntimeError):
    """A profile cannot be applied to these measurements."""


def build_constraints(
    profile: Profile, size: OutputSize, measurements: MeasurementSet
) -> tuple[list[Constraint], list[str]]:
    """Turn a profile into solver constraints for one output size.

    Returns the constraints and a list of rules that could not be applied, each with the
    reason. An unapplied rule is never silently dropped and never assumed satisfied.
    """
    if profile.reference_size and (
        size.width != profile.reference_size.width
        or size.height != profile.reference_size.height
    ):
        raise ProfileError(
            f"{profile.key} states its pixel rules at "
            f"{profile.reference_size.width}x{profile.reference_size.height} "
            f'"as an example" and never says whether they scale. Solving at '
            f"{size.width}x{size.height} would require an interpretation policy this build "
            "does not have. Use the reference size."
        )

    unapplied: list[str] = []
    constraints: list[Constraint] = []

    def to_px(rule: Rule, bound: float | None) -> float | None:
        """A rule's bound in output pixels. Vertical rules use the vertical scale; the two agree
        when the output size honours the printed aspect, and differ otherwise, which is itself
        a profile error worth surfacing."""
        if bound is None or rule.unit == "px":
            return bound
        if rule.unit == "fraction_height":
            return bound * size.height
        if rule.unit != "mm":
            raise ProfileError(f"{profile.key}/{rule.key}: unknown unit {rule.unit!r}")
        if profile.physical_mm is None:
            raise ProfileError(
                f"{profile.key}/{rule.key} is stated in mm but the profile has no physical size"
            )
        width_mm, height_mm = profile.physical_mm
        px_per_mm_x, px_per_mm_y = size.width / width_mm, size.height / height_mm
        if abs(px_per_mm_x - px_per_mm_y) / px_per_mm_y > 0.01:
            raise ProfileError(
                f"{profile.key}: output {size.width}x{size.height} does not honour the printed "
                f"aspect {width_mm}x{height_mm} mm"
            )
        return bound * px_per_mm_y

    # Observed-tier names. A profile binds to what was observed - the top row of the matte,
    # the chin vertex the mesh placed - and says so; see docs/STAGE1B-PRECONDITIONS.md.
    crown = measurements.value("matte_top_row")
    chin = measurements.value("chin_landmark_y")
    eye_line = measurements.value("eye_line_y")
    eye_x = measurements.value("eye_mid_x")
    head_width = measurements.value("head_width_silhouette")
    ied = measurements.value("inter_eye_distance")

    for rule in profile.rules:
        if rule.key == "face_width" or rule.key == "head_width":
            if head_width is None:
                unapplied.append(f"{rule.key}: head_width_silhouette is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=head_width, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                                       lo_strict=rule.lo_strict, hi_strict=rule.hi_strict))
        elif rule.key == "crown_gap":
            if crown is None:
                unapplied.append(f"{rule.key}: matte_top_row is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=crown, b=-1.0, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                                       lo_strict=rule.lo_strict, hi_strict=rule.hi_strict))
        elif rule.key == "eye_line_from_bottom":
            if eye_line is None:
                unapplied.append(f"{rule.key}: eye_line_y is unavailable")
                continue
            constraints.append(Constraint(
                rule.key, a=-eye_line, b=1.0, k=float(size.height), lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                lo_strict=rule.lo_strict, hi_strict=rule.hi_strict,
            ))
        elif rule.key == "head_height":
            if crown is None or chin is None:
                unapplied.append(f"{rule.key}: matte_top_row or chin_landmark_y is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=chin - crown, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                                       lo_strict=rule.lo_strict, hi_strict=rule.hi_strict))
        elif rule.key == "chin_to_bottom":
            if chin is None:
                unapplied.append(f"{rule.key}: chin_landmark_y is unavailable")
                continue
            constraints.append(Constraint(
                rule.key, a=-chin, b=1.0, k=float(size.height), lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                lo_strict=rule.lo_strict, hi_strict=rule.hi_strict,
            ))
        elif rule.key == "inter_eye_distance":
            if ied is None:
                unapplied.append(f"{rule.key}: inter_eye_distance is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=ied, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi),
                                       lo_strict=rule.lo_strict, hi_strict=rule.hi_strict))
        else:  # pragma: no cover - guards against a rule added without a handler
            unapplied.append(f"{rule.key}: no handler in this build")

    # Horizontal placement. No source surveyed states a numeric band, so this is a tool
    # PREFERENCE rather than anyone's law: keep the eye midpoint within the middle tenth
    # where the rules leave room, and never let it make a compliant crop infeasible.
    if eye_x is not None:
        constraints.append(Constraint(
            "eye_centred", a=eye_x, c=-1.0,
            lo=0.45 * size.width, hi=0.55 * size.width, preference=True,
        ))
    else:
        unapplied.append("eye_centred: eye_mid_x is unavailable")

    constraints.extend((
        Constraint("source_left", c=1.0, lo=0.0, hard=True),
        Constraint("source_top", b=1.0, lo=0.0, hard=True),
        Constraint("source_right", a=float(measurements.image_width), c=-1.0,
                   lo=float(size.width), hard=True),
        Constraint("source_bottom", a=float(measurements.image_height), b=-1.0,
                   lo=float(size.height), hard=True),
    ))
    return constraints, unapplied
