"""Encoding: write the rendered image within the channel's file limits, or say why not.

A byte band alone permits visibly poor output and can be unreachable at any acceptable quality,
so the search is bounded: a fixed list of qualities, the written file measured each time, the
highest quality inside the band wins. Nothing fitting is the result - reported with every size
tried - never a file padded to reach a floor or degraded past the list. Candidates are staged
beside the destination and replace it only on success, so whatever was at `out` survives a
failed search or a failed write.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from .profiles import Encoding

# Highest first, every integer step: a destination's band can be narrow (the US cap of 20:1 at
# 1200x1200 leaves 216,000-240,000 bytes, 10% wide) and coarser steps can jump over it. 70 is
# the floor of the search - a tool choice: below it a 354-px-wide face is visibly degraded on
# inspection, so the search stops there rather than squeezing a file into a band at a quality
# nobody should submit. It is not a published threshold.
JPEG_QUALITIES: tuple[int, ...] = tuple(range(98, 69, -1))

# Pillow's JPEG subsampling codes.
_SUBSAMPLING = {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}


@dataclass
class EncodeResult:
    status: str
    """`done`; `no_encoding_satisfies` (no listed quality fits the band; nothing written); or
    `write_failed` (the destination could not be written; the reason is in `detail`)."""
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


def _within(size: int, floor: int | None, ceiling: int | None) -> bool:
    if floor is not None and size < floor:
        return False
    if ceiling is not None and size > ceiling:
        return False
    return True


def _pixels_only(image):
    """A fresh RGB image holding only the pixels. Pillow copies `info` entries such as a JPEG
    COM comment from the image being saved into the file it writes; an image built from raw
    bytes carries none of them, whatever the source had."""
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    return Image.frombytes("RGB", rgb.size, rgb.tobytes())


class _Staged:
    """A temporary file beside `out`. `commit()` moves it into place; `discard()` removes it and
    returns a message if it could not. Whatever is at `out` is untouched until a commit."""

    def __init__(self, out: Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=out.parent, prefix=out.name + ".", suffix=".part")
        os.close(fd)
        self.out = out
        self.path: Path | None = Path(name)

    def commit(self) -> None:
        assert self.path is not None
        os.replace(self.path, self.out)
        self.path = None

    def discard(self) -> str | None:
        if self.path is None:
            return None
        try:
            self.path.unlink(missing_ok=True)
        except OSError as e:
            return f"could not remove {self.path}: {e}"
        self.path = None
        return None


def _search(image, encoding: Encoding, staged: _Staged, trace: list[dict[str, Any]]) -> EncodeResult:
    # The floor at this size: the readings' intersection, raised by a compression-ratio cap
    # where the source states one (a cap on the ratio is a floor on bytes).
    floor = encoding.min_bytes_for(*image.size)
    ceiling = encoding.max_bytes
    for quality in JPEG_QUALITIES:
        # Write, then measure the file on disk: the number that matters is the one the
        # applicant's upload form will see, after every byte the encoder emits. Every listed
        # quality is tried - file size is not monotone in quality at small sizes.
        image.save(staged.path, format="JPEG", quality=quality,
                   subsampling=_SUBSAMPLING[encoding.subsampling])
        size = staged.path.stat().st_size
        fits = _within(size, floor, ceiling)
        trace.append({"quality": quality, "bytes": size, "fits": fits})
        if fits:
            staged.commit()
            return EncodeResult("done", staged.out, quality, size, trace,
                                f"quality {quality}, {size} bytes")
    band = f"{floor or 0}-{ceiling or 'inf'} bytes at {image.size[0]}x{image.size[1]}"
    if encoding.max_compression_ratio is not None and floor is not None and floor > (encoding.min_bytes or 0):
        band += f" (floor from the {encoding.max_compression_ratio:g}:1 compression cap)"
    return EncodeResult("no_encoding_satisfies", None, None, None, trace,
                        f"no listed JPEG quality produced a file within {band}; nothing written")


def encode(image, encoding: Encoding, out: Path) -> EncodeResult:
    """Write `image` to `out` at the highest listed quality whose written size fits the band."""
    if encoding.format != "jpeg":
        return EncodeResult("no_encoding_satisfies", None, None, None,
                            detail=f"format {encoding.format!r} is not supported by this build")
    if encoding.colour != "srgb_24bit":
        return EncodeResult("no_encoding_satisfies", None, None, None,
                            detail=f"colour {encoding.colour!r} is not supported by this build")

    out = Path(out)
    trace: list[dict[str, Any]] = []
    staged: _Staged | None = None
    try:
        staged = _Staged(out)
        result = _search(_pixels_only(image), encoding, staged, trace)
    except OSError as e:
        result = EncodeResult("write_failed", None, None, None, trace,
                              f"could not write {out}: {e}")
    if staged is not None:
        leftover = staged.discard()
        if leftover:
            result.detail += f"; cleanup failed: {leftover}"
    return result
