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
    unit: str = "px"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "quote": self.quote, "measurement": self.measurement,
            "lo": self.lo, "hi": self.hi, "unit": self.unit, "note": self.note,
        }


@dataclass(frozen=True)
class Encoding:
    """A channel's published file-format rules. Absent when the channel is a print."""

    format: str
    colour: str
    min_bytes: int | None
    max_bytes: int | None
    quote: str
    subsampling: str = "4:4:4"
    """Chroma subsampling for JPEG output. Not published by any source surveyed; 4:4:4 is
    this tool's choice, because a 354-px-wide face has no chroma to spare."""

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "colour": self.colour, "min_bytes": self.min_bytes,
                "max_bytes": self.max_bytes, "subsampling": self.subsampling, "quote": self.quote}


OPERATIONS: tuple[str, ...] = (
    "crop", "resize", "encode", "rotate", "replace_background", "adjust_colour",
    "synthesize_pixels",
)


@dataclass(frozen=True)
class OutputSize:
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass(frozen=True)
class Profile:
    key: str
    destination: str
    channel: str
    source: str
    retrieved: str
    sizes: tuple[OutputSize, ...]
    rules: tuple[Rule, ...]
    physical_mm: tuple[float, float] | None = None
    """Printed size, when the rules are stated in millimetres. Bounds in mm are converted to
    output pixels through this and the output size before any constraint is built - a pixel
    measurement compared against a millimetre bound rejects every photograph."""

    reference_size: OutputSize | None = None
    """The size at which pixel-denominated rules were stated. China gives its pixel figures
    "as an example" at 354x472 and never says whether they scale. We therefore apply them
    literally and only at sizes we can justify - see `sizes_for_pixel_rules`."""

    operations: dict[str, str] = field(default_factory=dict)
    encoding: Encoding | None = None
    notes: tuple[str, ...] = ()

    def policy(self, operation: str) -> str:
        """allowed / prohibited / unresolved. Unstated is unresolved - never allowed by default.

        Doing something a channel has not addressed, to an identity photograph, is not a
        decision this tool makes for the applicant. See docs/STAGE3-RENDER.md.
        """
        if operation not in OPERATIONS:
            raise ValueError(f"unknown operation {operation!r}")
        return self.operations.get(operation, "unresolved")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "destination": self.destination, "channel": self.channel,
            "source": self.source, "retrieved": self.retrieved,
            "sizes": [{"width": s.width, "height": s.height} for s in self.sizes],
            "reference_size": (
                {"width": self.reference_size.width, "height": self.reference_size.height}
                if self.reference_size else None
            ),
            "rules": [r.to_dict() for r in self.rules],
            "operations": {op: self.policy(op) for op in OPERATIONS},
            "encoding": self.encoding.to_dict() if self.encoding else None,
            "notes": list(self.notes),
        }


# --- China, online application (digital) --------------------------------------------------
# NOTE what is NOT here: this channel states no head-height bound and no chin-to-bottom-edge
# bound. Both exist only in the paper profile, in millimetres. Their absence is the point.
CN_VISA_DIGITAL = Profile(
    key="cn_visa_digital",
    destination="China",
    channel="online visa application (digital photo)",
    source=CN_SHEET,
    retrieved="2026-09-04",
    sizes=(OutputSize(354, 472), OutputSize(420, 560)),
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
            lo=256.0,
        ),
        Rule(
            key="inter_eye_distance",
            quote="The inter-eye distance should be > 60 pixels.",
            measurement="inter_eye_distance",
            lo=60.0,
        ),
    ),
    operations={
        "crop": "allowed", "resize": "allowed", "encode": "allowed",
        "rotate": "unresolved", "replace_background": "unresolved",
        "adjust_colour": "unresolved", "synthesize_pixels": "prohibited",
    },
    encoding=Encoding(
        format="jpeg", colour="srgb_24bit", min_bytes=40 * 1024, max_bytes=120 * 1024,
        quote="JPEG and the image file size: 40 KB - 120 KB. ... RGB 24bit true colour.",
    ),
    notes=(
        "This channel states NO head-height bound. Do not import one from the paper profile.",
        "MFA allows up to 420x560; the CVASC upload FAQ says photos cannot exceed 354x472.",
    ),
)


CN_VISA_PAPER = Profile(
    key="cn_visa_paper",
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


PROFILES: dict[str, Profile] = {p.key: p for p in (CN_VISA_DIGITAL, CN_VISA_PAPER)}


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
            constraints.append(Constraint(rule.key, a=head_width, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)))
        elif rule.key == "crown_gap":
            if crown is None:
                unapplied.append(f"{rule.key}: matte_top_row is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=crown, b=-1.0, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)))
        elif rule.key == "eye_line_from_bottom":
            if eye_line is None:
                unapplied.append(f"{rule.key}: eye_line_y is unavailable")
                continue
            constraints.append(Constraint(
                rule.key, a=-eye_line, b=1.0, k=float(size.height), lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)
            ))
        elif rule.key == "head_height":
            if crown is None or chin is None:
                unapplied.append(f"{rule.key}: matte_top_row or chin_landmark_y is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=chin - crown, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)))
        elif rule.key == "chin_to_bottom":
            if chin is None:
                unapplied.append(f"{rule.key}: chin_landmark_y is unavailable")
                continue
            constraints.append(Constraint(
                rule.key, a=-chin, b=1.0, k=float(size.height), lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)
            ))
        elif rule.key == "inter_eye_distance":
            if ied is None:
                unapplied.append(f"{rule.key}: inter_eye_distance is unavailable")
                continue
            constraints.append(Constraint(rule.key, a=ied, lo=to_px(rule, rule.lo), hi=to_px(rule, rule.hi)))
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
