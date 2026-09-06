"""Command line entry point.

Exit codes are distinct on purpose, so a caller (a script, or a Claude skill) can tell the
difference between "this photo has a problem" and "this tool broke":

    0  measured successfully, no advisory warnings raised
    1  measured successfully, one or more advisory warnings raised
    2  could not measure (no face, several faces, unreadable image, missing model)
    3  usage or configuration error
    4  measured fine, but no crop can satisfy the requested profile
    5  a crop was found, but no file could be written within the profile's encoding rules
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .geometry import Infeasible, Solution
from .encode import encode
from .measure import MeasurementError, load_source, measure_photo
from .plan import make_plan
from .preflight import Outcome
from .profiles import PROFILES
from .render import render

EXIT_OK = 0
EXIT_WARNINGS = 1
EXIT_CANNOT_MEASURE = 2
EXIT_USAGE = 3
EXIT_NO_CROP = 4
EXIT_NOT_WRITTEN = 5

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


def _render_plan(plan) -> None:
    print(f"\nplan ({plan.profile.key}: {plan.profile.destination}, {plan.profile.channel})")

    for attempt in plan.attempts:
        label = f"{attempt.size.width}x{attempt.size.height}"
        if attempt.skipped:
            print(f"  {label:<10} skipped   {attempt.skipped}")
        elif attempt.blocked:
            print(f"  {label:<10} BLOCKED   {attempt.blocked}")
        elif isinstance(attempt.outcome, Infeasible):
            print(f"  {label:<10} NO CROP   {attempt.outcome.detail}")
            for left, right in attempt.outcome.conflicting_rules[:4]:
                print(f"  {'':<10}           conflict: {left} vs {right}")
            for rule, (lo, hi) in attempt.outcome.scale_bands.items():
                print(f"  {'':<10}           {rule} admits scale [{lo:.4f}, {hi:.4f}]")
        else:
            print(f"  {label:<10} ok        slack {attempt.outcome.min_slack:+.3f}")

    chosen = plan.chosen
    if chosen is None:
        print("\n  No output size satisfies this profile for this photograph.")
        return

    solution = chosen.outcome
    print(f"\n  chosen  {chosen.size.width}x{chosen.size.height}")
    print(f"  scale   {solution.scale:.5f}")
    print(f"  crop    x={solution.crop_x:.1f} y={solution.crop_y:.1f} "
          f"w={chosen.size.width / solution.scale:.1f} h={chosen.size.height / solution.scale:.1f}")
    print("  slack per rule (0 = on a limit):")
    for rule, value in sorted(solution.slacks.items()):
        if not rule.startswith("source"):
            print(f"    {rule:<24} {value:+.3f}")
    for unapplied in chosen.unapplied:
        print(f"  NOT APPLIED  {unapplied}")
    for note in plan.profile.notes:
        print(f"  note  {note}")
def _capabilities(as_json: bool) -> int:
    """The capability matrix, generated from the registry. Works with nothing installed."""
    from .gates import GATE_SPECS
    from .registry import capabilities

    rows = capabilities()
    if as_json:
        json.dump({"measurements": rows,
                   "gates": [{"id": g.id, "method": g.method, "prerequisites": list(g.prerequisites),
                              "always_unknown": g.always_none} for g in GATE_SPECS]},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return EXIT_OK
    for row in rows:
        marker = "  " if row["available_in_this_build"] else "x "
        print(f"{marker}{row['measurement']:<30} {row['tier']:<10} {row['unit']:<9} {row['backend']}")
        print(f"    {row['definition']}")
        print(f"    requires: {', '.join(row['required_gates'])}")
        if row["always_unknown_gates"]:
            print(f"    NEVER AVAILABLE in this build: {', '.join(row['always_unknown_gates'])} "
                  "cannot be evaluated")
    print("\nx = unavailable on every image this build can process")
    return EXIT_OK


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
        "--capabilities", action="store_true",
        help="print what this build can measure, and under which conditions, then exit. "
             "Needs no model weights.",
    )
    parser.add_argument(
        "--for", dest="jurisdiction", default=None, metavar="CODE",
        help="where the photo is going (e.g. CN, US, EU, NZ). Omit for generic advisories.",
    )
    parser.add_argument("--model", type=Path, default=None,
                        help="path to the MediaPipe face_landmarker .task bundle")
    parser.add_argument(
        "--spec", default=None, metavar="PROFILE",
        help="plan a crop against a destination profile (see --list-specs)",
    )
    parser.add_argument(
        "--list-specs", action="store_true", help="list available profiles and exit",
    )
    parser.add_argument(
        "--out", type=Path, default=None, metavar="FILE",
        help="render the planned crop and write it here (requires --spec, digital profiles only)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--no-segmentation", action="store_true",
                        help="skip the person matte (faster; no crown or silhouette width)")
    args = parser.parse_args(argv)

    if args.list_specs:
        for key, profile in sorted(PROFILES.items()):
            sizes = ", ".join(f"{s.width}x{s.height}" for s in profile.sizes)
            print(f"{key:<20} {profile.destination} - {profile.channel}")
            print(f"{'':<20} sizes: {sizes}")
        return EXIT_OK

    if args.spec is not None and args.spec not in PROFILES:
        print(
            f"error: no profile '{args.spec}'. This tool will not invent a specification.\n"
            f"       Known profiles: {', '.join(sorted(PROFILES))}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.capabilities:
        return _capabilities(as_json=args.json)

    if args.fetch_models:
        return _fetch_models()

    if args.photo is None:
        parser.error("a photo is required unless --fetch-models or --capabilities is given")
    if not args.photo.is_file():
        print(f"error: no such file: {args.photo}", file=sys.stderr)
        return EXIT_USAGE

    if args.out is not None:
        if args.spec is None:
            print("error: --out requires --spec: a file is rendered for one destination profile",
                  file=sys.stderr)
            return EXIT_USAGE
        if PROFILES[args.spec].encoding is None:
            print(f"error: {args.spec} states no digital encoding rules; --out is not supported "
                  "for print profiles yet", file=sys.stderr)
            return EXIT_USAGE
        if args.out.exists() and args.out.resolve() == args.photo.resolve():
            print("error: --out is the input photo; the original is never overwritten",
                  file=sys.stderr)
            return EXIT_USAGE

    try:
        # One decode: measurement and rendering work from the same pixels.
        source = load_source(args.photo)
        measurements, preflight = measure_photo(
            args.photo,
            model=args.model,
            jurisdiction=args.jurisdiction,
            segmentation_enabled=not args.no_segmentation,
            source=source,
        )
    except MeasurementError as exc:
        print(f"cannot measure: {exc}", file=sys.stderr)
        return EXIT_CANNOT_MEASURE

    face = measurements.gate_record["face_detected_one"]
    cannot_measure = face.satisfied is not True
    if cannot_measure:
        print(f"cannot measure: {face.detail}", file=sys.stderr)
    plan = make_plan(PROFILES[args.spec], measurements) if args.spec else None

    rendered = encoded = None
    if args.out is not None and plan is not None and plan.feasible and not cannot_measure:
        rendered = render(source, plan)
        if rendered.rendered:
            encoded = encode(rendered.image, PROFILES[args.spec].encoding, args.out)

    if args.json:
        json.dump(
            {
                "measurements": measurements.to_dict(),
                "preflight": preflight.to_dict(),
                "plan": plan.to_dict() if plan else None,
                "render": rendered.to_dict() if rendered else None,
                "encode": encoded.to_dict() if encoded else None,
            },
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        _render(measurements, preflight)
        if plan:
            _render_plan(plan)
        if rendered:
            _render_history(rendered, encoded)

    # The report is emitted in every case so a caller can see what was established; the exit
    # code still says the photo could not be measured. Checked before plan feasibility, so a
    # missing face is never mistaken for a geometric refusal.
    if cannot_measure:
        return EXIT_CANNOT_MEASURE
    if plan and not plan.feasible:
        return EXIT_NO_CROP
    if args.out is not None and (encoded is None or not encoded.done):
        return EXIT_NOT_WRITTEN
    return EXIT_WARNINGS if preflight.warnings else EXIT_OK


def _render_history(rendered, encoded) -> None:
    print("\noperations")
    for h in rendered.history:
        print(f"  {h.name:<16} {h.status:<8} {h.detail}")
        if h.name == "crop_resize" and h.status == "done":
            box = ", ".join(f"{v:.2f}" for v in h.params["box"])
            out = h.params["output"]
            print(f"  {'':<16}          box ({box}) scale {h.params['scale']:.5f} "
                  f"-> {out['width']}x{out['height']}")
    if encoded is not None:
        print(f"  {'encode':<16} {encoded.status:<8} {encoded.detail}")
        for t in encoded.trace:
            print(f"  {'':<16}          q{t['quality']}: {t['bytes']} bytes"
                  f"{' <- chosen' if t['fits'] else ''}")
    if encoded is not None and encoded.done:
        print(f"\n  written: {encoded.path}")
    else:
        print("\n  NOT WRITTEN")


if __name__ == "__main__":
    sys.exit(main())
