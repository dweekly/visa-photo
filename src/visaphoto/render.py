"""Rendering: turn a feasible plan into pixels. Colour to sRGB, then one resample.

The plan is the only input that carries authority; nothing here adds a judgement of its own.
Every step is recorded so the report can say what was done to the photograph, in order, and
claim nothing else. See docs/STAGE3-RENDER.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .geometry import EPS
from .measure import Source
from .plan import Plan


@dataclass(frozen=True)
class OperationRecord:
    """One operation's outcome: `done`, `skipped` (with the assumption made instead), or
    `refused` (with why)."""

    name: str
    status: str
    detail: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"operation": self.name, "status": self.status, "detail": self.detail,
                "params": self.params}


@dataclass
class RenderResult:
    image: Any
    """PIL RGB image at the chosen output size, or None when rendering was refused."""
    history: list[OperationRecord]

    @property
    def rendered(self) -> bool:
        return self.image is not None

    def to_dict(self) -> dict[str, Any]:
        return {"rendered": self.rendered, "history": [h.to_dict() for h in self.history]}


def _convert_to_srgb(native) -> tuple[Any, OperationRecord]:
    """Convert the native image to sRGB through its embedded ICC profile.

    Phone photographs carry Display P3; writing their channel values into a JPEG with no profile
    would change the colours on every viewer. Without a profile - or with one LittleCMS cannot
    parse, or one it parses but cannot apply - the pixels are taken as sRGB, and the record
    says which of the three it was. Relative colorimetric: a display-to-display conversion
    keeps in-gamut colours exact and clips the rest.
    """
    import io
    from PIL import ImageCms

    def assumed(reason: str):
        rgb = native if native.mode == "RGB" else native.convert("RGB")
        return rgb, OperationRecord("colour_convert", "skipped", f"assumed sRGB: {reason}")

    icc = native.info.get("icc_profile")
    if not icc:
        return assumed("no embedded profile")
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        name = ImageCms.getProfileDescription(profile).strip()
    except (ImageCms.PyCMSError, OSError) as e:  # LittleCMS raises OSError on bytes it cannot parse
        return assumed(f"profile unreadable ({e})")
    try:
        converted = ImageCms.profileToProfile(
            native, profile, ImageCms.createProfile("sRGB"),
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC, outputMode="RGB")
    except (ImageCms.PyCMSError, OSError, ValueError) as e:
        return assumed(f"conversion from '{name}' failed: {e}")
    return converted, OperationRecord(
        "colour_convert", "done", f"converted from '{name}' to sRGB, relative colorimetric",
        {"from": name, "to": "sRGB", "intent": "relative_colorimetric"})


def _crop_box(plan: Plan, source_size: tuple[int, int]) -> tuple[float, float, float, float]:
    """The plan's crop as a Pillow box, clamped to the source at the solver's tolerance.

    Containment is a hard constraint in the solver, so an edge can land a rounding error outside
    the source (an origin of -3e-14 was produced for a crop touching the left edge); Pillow
    rejects that outright. Inside `EPS` is noise and is clamped; further out is a solver defect
    and raises rather than being quietly moved.
    """
    o = plan.chosen.outcome
    w, h = source_size
    raw = (o.crop_x, o.crop_y,
           o.crop_x + plan.chosen.size.width / o.scale,
           o.crop_y + plan.chosen.size.height / o.scale)
    limits = (0.0, 0.0, float(w), float(h))
    box = []
    for value, limit, is_lower in zip(raw, limits, (True, True, False, False)):
        outside = (limit - value) if is_lower else (value - limit)
        if outside > EPS:
            raise ValueError(f"plan crop {raw} lies outside the {w}x{h} source by {outside}")
        box.append(limit if outside > 0 else value)
    return tuple(box)


def render(source: Source, plan: Plan) -> RenderResult:
    """Apply the plan's crop to the decoded source. Colour first, then one resample."""
    from PIL import Image

    history: list[OperationRecord] = []
    if not plan.feasible:
        history.append(OperationRecord("crop_resize", "refused", "no feasible crop in the plan"))
        return RenderResult(None, history)

    image, colour = _convert_to_srgb(source.native)
    history.append(colour)

    box = _crop_box(plan, image.size)
    size = (plan.chosen.size.width, plan.chosen.size.height)
    out = image.resize(size, Image.Resampling.LANCZOS, box=box)
    history.append(OperationRecord(
        "crop_resize", "done", "single Lanczos resample through a float crop box",
        {"box": list(box), "scale": plan.chosen.outcome.scale,
         "output": {"width": size[0], "height": size[1]}}))
    return RenderResult(out, history)
