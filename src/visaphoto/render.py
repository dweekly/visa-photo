"""Rendering: turn a feasible plan into pixels, one gated operation at a time.

Each operation is built the way a measurement is after Stage 1b: a name, gates looked up from
the record, and a status decided from those gates - never from whether the inputs happened to
be present. A background is not replaced because a matte exists; it is replaced because the
channel permits it, the matte isolated the face, and the subject does not cross the crop's
top or sides. See docs/STAGE3-RENDER.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .measurements import MeasurementSet
from .plan import Plan
from .profiles import Profile

WHITE = (255, 255, 255)


@dataclass(frozen=True)
class OperationRecord:
    """One operation's outcome. `done`, `skipped` (policy) or `refused` (a gate failed)."""

    name: str
    status: str
    detail: str
    gates: tuple[tuple[str, bool | None, str], ...] = ()
    params: dict[str, Any] = field(default_factory=dict)
    opt_in: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.name, "status": self.status, "detail": self.detail,
            "gates": [{"id": g, "satisfied": s, "detail": d} for g, s, d in self.gates],
            "params": self.params, "opt_in": self.opt_in,
        }


@dataclass
class RenderResult:
    image: Any
    """PIL RGB image at the chosen output size, or None if rendering was refused."""
    history: list[OperationRecord]

    @property
    def rendered(self) -> bool:
        return self.image is not None

    def to_dict(self) -> dict[str, Any]:
        return {"rendered": self.rendered, "history": [h.to_dict() for h in self.history]}


def _gate(measurements: MeasurementSet, gate_id: str) -> tuple[str, bool | None, str]:
    g = measurements.gate_record[gate_id]
    return (gate_id, g.satisfied, g.detail)


def _crop_box(plan: Plan) -> tuple[float, float, float, float]:
    chosen = plan.chosen
    s = chosen.outcome.scale
    x0, y0 = chosen.outcome.crop_x, chosen.outcome.crop_y
    return (x0, y0, x0 + chosen.size.width / s, y0 + chosen.size.height / s)


def _subject_clear_of_crop_top_and_sides(alpha, box, solid_threshold: int) -> tuple[bool, str]:
    """The matte must not cross the crop's top or side edges. The bottom is exempt: a
    head-and-shoulders crop necessarily cuts through the torso."""
    import numpy as np

    x0, y0, x1, y1 = (int(round(v)) for v in box)
    h, w = alpha.shape
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    solid = alpha > solid_threshold
    top = bool(solid[y0, x0:x1].any()) if 0 <= y0 < h else False
    left = bool(solid[y0:y1, x0].any()) if 0 <= x0 < w else False
    right = bool(solid[y0:y1, x1 - 1].any()) if 0 < x1 <= w else False
    crossing = [n for n, t in (("top", top), ("left", left), ("right", right)) if t]
    if crossing:
        return False, f"the subject crosses the crop's {', '.join(crossing)} edge"
    return True, "subject clear of the crop's top and sides"


def render(
    image_rgb, measurements: MeasurementSet, plan: Plan, profile: Profile, *,
    allow_unresolved: bool = False,
) -> RenderResult:
    """Apply the plan's crop to `image_rgb`, replacing the background first where permitted.

    Returns the image and a complete history. Refusing an operation the channel prohibits is
    a successful outcome of this function, recorded as such; a refused *crop* means no image.
    """
    from PIL import Image
    from .backends.segmentation import ALPHA_SOLID

    history: list[OperationRecord] = []
    source = image_rgb

    if not plan.feasible:
        history.append(OperationRecord("crop_resize", "refused", "no feasible crop in the plan"))
        return RenderResult(None, history)

    # --- replace_background, in source space, before the resample ------------------------
    policy = profile.policy("replace_background")
    bg_gates = (_gate(measurements, "matte_present"),
                _gate(measurements, "face_component_isolated"))
    if policy == "prohibited":
        history.append(OperationRecord(
            "replace_background", "skipped",
            f"{profile.key} prohibits background replacement", bg_gates))
    elif policy == "unresolved" and not allow_unresolved:
        history.append(OperationRecord(
            "replace_background", "skipped",
            f"{profile.key} does not address background replacement; not performed without "
            "--allow-unresolved-operations", bg_gates))
    elif any(s is not True for _, s, _ in bg_gates):
        history.append(OperationRecord(
            "replace_background", "refused",
            "the matte did not establish the face's region; a background cannot be replaced "
            "from it", bg_gates, opt_in=policy == "unresolved"))
    else:
        clear, why = _subject_clear_of_crop_top_and_sides(
            measurements.matte_alpha, _crop_box(plan), ALPHA_SOLID)
        edge_gate = ("subject_clear_of_crop_top_and_sides", clear, why)
        if not clear:
            history.append(OperationRecord(
                "replace_background", "refused", why, (*bg_gates, edge_gate),
                opt_in=policy == "unresolved"))
        else:
            matte = Image.fromarray(measurements.matte_alpha, "L")
            backdrop = Image.new("RGB", source.size, WHITE)
            source = Image.composite(source, backdrop, matte)
            history.append(OperationRecord(
                "replace_background", "done",
                "composited the person matte over white in source space",
                (*bg_gates, edge_gate), {"background": "#ffffff"},
                opt_in=policy == "unresolved"))

    # --- crop + resize: one uniform resample through a float box --------------------------
    for op in ("crop", "resize"):
        if profile.policy(op) != "allowed":
            history.append(OperationRecord(
                "crop_resize", "refused", f"{profile.key} does not allow {op}"))
            return RenderResult(None, history)
    box = _crop_box(plan)
    size = (plan.chosen.size.width, plan.chosen.size.height)
    out = source.resize(size, Image.Resampling.LANCZOS, box=box)
    history.append(OperationRecord(
        "crop_resize", "done", "single Lanczos resample through a float crop box",
        params={"box": [round(v, 2) for v in box], "scale": plan.chosen.outcome.scale,
                "output": {"width": size[0], "height": size[1]}}))

    history.append(OperationRecord(
        "colour_convert", "skipped",
        "the source's embedded colour profile was not consulted; sRGB is assumed and the "
        "output is written as sRGB without a profile"))
    return RenderResult(out, history)
