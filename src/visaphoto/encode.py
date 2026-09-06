"""Encoding: write the rendered image within the channel's published file limits, or say why not.

A byte band alone permits visibly poor output and may be unreachable at any acceptable
quality. So the search is bounded: a fixed list of qualities, the written file's bytes measured
each time, highest quality inside the band wins. If nothing fits, that is the result - reported
with the trace - never a file padded to reach a floor or degraded past the list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import ImageFile

from .profiles import Encoding

# Highest first. Below 70 a 354-px-wide portrait is visibly degraded, so the search stops
# there rather than squeezing a file into a band at a quality nobody should submit.
JPEG_QUALITIES: tuple[int, ...] = (98, 96, 94, 92, 90, 88, 85, 82, 80, 75, 70)

# libjpeg's Huffman-table optimization needs the whole entropy-coded output in one buffer.
# Pillow sizes that buffer at 2 x width x height bytes for quality >= 95 and 1 x below (see
# PIL/JpegImagePlugin.py `_save`, "if optimize or progressive"), and high-entropy 4:4:4
# content overruns it: the encoder then fails with "broken data stream when writing image
# file". `ImageFile.MAXBLOCK` is the floor Pillow applies to that estimate (`ImageFile._save`,
# "FIXME: make MAXBLOCK a configuration parameter"), so it is raised to a multiple of the raw
# pixel byte count for the duration of the save. Measured worst case on Pillow 12.3.0 - 354x472
# uniform random noise, quality 98, 4:4:4, optimized - is 0.83 x raw bytes (417,443 of 501,264).
# The multiple is an empirical margin over that measurement, not a bound on JPEG output.
ENCODER_BUFFER_RAW_MULTIPLE = 2

# Pillow's JPEG subsampling codes.
_SUBSAMPLING = {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}


@dataclass
class EncodeResult:
    status: str
    """`done` or `no_encoding_satisfies`."""
    path: Path | None
    quality: int | None
    bytes: int | None
    trace: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""

    @property
    def done(self) -> bool:
        return self.status == "done"

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "path": str(self.path) if self.path else None,
                "quality": self.quality, "bytes": self.bytes, "trace": self.trace,
                "detail": self.detail}


def _within(size: int, encoding: Encoding) -> bool:
    if encoding.min_bytes is not None and size < encoding.min_bytes:
        return False
    if encoding.max_bytes is not None and size > encoding.max_bytes:
        return False
    return True


def encode(image, encoding: Encoding, out: Path) -> EncodeResult:
    """Write `image` to `out` at the highest listed quality whose written size fits the band."""
    if encoding.format != "jpeg":
        return EncodeResult("no_encoding_satisfies", None, None, None,
                            detail=f"format {encoding.format!r} is not supported by this build")
    if encoding.colour != "srgb_24bit":
        return EncodeResult("no_encoding_satisfies", None, None, None,
                            detail=f"colour {encoding.colour!r} is not supported by this build")

    if image.mode != "RGB":
        image = image.convert("RGB")  # the colour spec is 24-bit sRGB; nothing else is written
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    trace: list[dict[str, Any]] = []
    raw_bytes = image.size[0] * image.size[1] * 3
    default_maxblock = ImageFile.MAXBLOCK
    ImageFile.MAXBLOCK = max(default_maxblock, raw_bytes * ENCODER_BUFFER_RAW_MULTIPLE)
    try:
        for quality in JPEG_QUALITIES:
            # Write, then measure the file on disk: the number that matters is the one the
            # applicant's upload form will see, after every byte the encoder emits.
            image.save(out, format="JPEG", quality=quality,
                       subsampling=_SUBSAMPLING[encoding.subsampling], optimize=True)
            size = os.path.getsize(out)
            fits = _within(size, encoding)
            trace.append({"quality": quality, "bytes": size, "fits": fits})
            if fits:
                return EncodeResult("done", out, quality, size, trace,
                                    f"quality {quality}, {size} bytes")
            if encoding.min_bytes is not None and size < encoding.min_bytes:
                break  # lower quality only gets smaller; nothing below will fit either
    finally:
        ImageFile.MAXBLOCK = default_maxblock

    out.unlink(missing_ok=True)
    band = f"{encoding.min_bytes or 0}-{encoding.max_bytes or 'inf'} bytes"
    return EncodeResult(
        "no_encoding_satisfies", None, None, None, trace,
        f"no listed JPEG quality produced a file within {band}; the output is not written",
    )
