"""Command line entry point.

Exit codes are distinct on purpose, so a caller (a script, or a Claude skill) can tell the
difference between "this photo has a problem" and "this tool broke":

    0  measured successfully, no advisory warnings raised
    1  measured successfully, one or more advisory warnings raised
    2  could not measure (no face, several faces, unreadable image, missing model)
    3  usage or configuration error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .measure import MeasurementError, measure_photo
from .preflight import Outcome

EXIT_OK = 0
EXIT_WARNINGS = 1
EXIT_CANNOT_MEASURE = 2
EXIT_USAGE = 3

_SYMBOL = {
    Outcome.LIKELY_OK: "ok  ",
    Outcome.WARN: "WARN",
    Outcome.NOT_EVALUATED: "-   ",
    Outcome.ATTESTATION_REQUIRED: "ask ",
    Outcome.OPERATION_POLICY: "note",
}


def _render(measurements, preflight) -> None:
    print(f"source   {measurements.source}")
    print(f"image    {measurements.image_width} x {measurements.image_height}")
    print(f"backends {', '.join(f'{k} {v}' for k, v in measurements.backends.items())}")

    print("\nmeasurements")
    for name, m in measurements.measurements.items():
        if m.available:
            unit = f" {m.unit}" if m.unit else ""
            advisory = "  (advisory)" if m.confidence and m.confidence.value == "advisory" else ""
            print(f"  {name:<24} {m.value:>10.1f}{unit}{advisory}")
        else:
            print(f"  {name:<24} {m.status.value:>10}   {m.reason}")

    print(f"\npre-flight ({preflight.mode}"
          + (f", {preflight.jurisdiction}" if preflight.jurisdiction else "") + ")")
    if preflight.mode == "unseeded":
        print(f"  No transcribed requirements for {preflight.jurisdiction}.")
        print("  This tool will not invent a specification. Run without --for to get generic")
        print("  advisories, or contribute a cited profile - see CONTRIBUTING.")
    for finding in preflight.findings:
        print(f"  [{_SYMBOL[finding.outcome]}] {finding.requirement.key}")
        print(f"         {finding.detail}")
        print(f'         "{finding.requirement.quote}"')

    warnings = preflight.warnings
    print()
    if warnings:
        print(f"{len(warnings)} advisory warning(s). These are uncalibrated heuristics, not a")
        print("compliance verdict - a human should look at the photo.")
    else:
        print("No advisory warnings. This is NOT a statement of compliance: geometry has not")
        print("been checked, and several requirements above could not be evaluated at all.")


def _fetch_models() -> int:
    """Download model weights. Kept separate from measurement on purpose: photo processing
    must never open a network connection, so that the offline promise is testable."""
    from .backends import segmentation
    from .measure import MODEL_URL, default_model_path

    landmark = default_model_path()
    if landmark.is_file():
        print(f"landmark model already present: {landmark}")
    else:
        print(f"downloading landmark model -> {landmark}")
        landmark.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        import urllib.request

        # Download to a sibling and rename on success. Writing straight to the final path
        # means an interrupted download leaves a truncated file that every later run treats
        # as installed, so an ordinary Ctrl-C makes the tool permanently broken with no way
        # to recover through the setup command itself.
        handle, temporary = tempfile.mkstemp(dir=landmark.parent, suffix=".partial")
        import os

        os.close(handle)
        temporary_path = Path(temporary)
        try:
            urllib.request.urlretrieve(MODEL_URL, temporary_path)
            temporary_path.replace(landmark)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        print("  done")

    weights = segmentation.model_path()
    if weights.is_file():
        print(f"segmentation model already present: {weights}")
    else:
        print(f"downloading segmentation model ({segmentation.MODEL_NAME}) -> {weights}")
        import rembg

        rembg.new_session(segmentation.MODEL_NAME)
        print("  done" if weights.is_file() else "  WARNING: weights still not at that path")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="visa-photo",
        description="Measure a portrait and check it against sourced photo requirements.",
    )
    parser.add_argument(
        "photo", type=Path, nargs="?",
        help="source photograph (omit with --fetch-models)",
    )
    parser.add_argument(
        "--fetch-models", action="store_true",
        help="download the model weights, then exit. The only command that uses the network.",
    )
    parser.add_argument(
        "--for", dest="jurisdiction", default=None, metavar="CODE",
        help="where the photo is going (e.g. CN, US, EU, NZ). Omit for generic advisories.",
    )
    parser.add_argument("--model", type=Path, default=None,
                        help="path to the MediaPipe face_landmarker .task bundle")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--no-segmentation", action="store_true",
                        help="skip the person matte (faster; no crown or silhouette width)")
    args = parser.parse_args(argv)

    if args.fetch_models:
        return _fetch_models()

    if args.photo is None:
        parser.error("a photo is required unless --fetch-models is given")
    if not args.photo.is_file():
        print(f"error: no such file: {args.photo}", file=sys.stderr)
        return EXIT_USAGE

    try:
        measurements, preflight = measure_photo(
            args.photo,
            model=args.model,
            jurisdiction=args.jurisdiction,
            segmentation=not args.no_segmentation,
        )
    except MeasurementError as exc:
        print(f"cannot measure: {exc}", file=sys.stderr)
        return EXIT_CANNOT_MEASURE

    if args.json:
        json.dump(
            {"measurements": measurements.to_dict(), "preflight": preflight.to_dict()},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        _render(measurements, preflight)

    return EXIT_WARNINGS if preflight.warnings else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
