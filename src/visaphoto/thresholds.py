"""Tunable heuristics, centralised so they can be found, criticised and calibrated.

READ THIS BEFORE USING ANY VALUE HERE.

None of these thresholds comes from a government requirement. No authority we surveyed
publishes a numeric threshold for "smiling", "eyes closed" or "mouth open" — see
docs/PLAN.md. Every number below is our own judgement about when to *advise a human to look
again*, chosen on a small number of images and not calibrated against a labelled dataset.

Consequences, which the code enforces:

* Crossing a threshold here produces an advisory `Flag`, never a compliance verdict.
* A flag says "this may need a retake", never "this photo is rejected".
* The score and the threshold are both reported, so a reader can disagree with us.

MediaPipe blendshape scores are in [0, 1]. They are model outputs whose calibration Google
does not document, so a score of 0.5 does not mean "half a smile" and the scale is not
guaranteed stable across model versions. That is a further reason these are advisory.

Reference observation (2026-09-04), one adult male subject, deliberately neutral expression,
front-lit, eyes open, mouth closed — the kind of photo that should raise nothing:

    mouthSmileLeft 0.0045   mouthSmileRight 0.0027
    jawOpen        0.0373
    eyeBlinkLeft   0.1452   eyeBlinkRight   0.0664
    browDownLeft   0.6488   browDownRight   0.7051
    eyeSquintLeft  0.4547   eyeSquintRight  0.4998

Note how high browDown and eyeSquint run on a photo with an unremarkable expression. That is
why no flag is raised on those two: on this evidence they would fire constantly. Anyone adding
a threshold for them needs more than one face.
"""

from __future__ import annotations

from typing import Final

# --- Expression flags -------------------------------------------------------------------
# Chosen to sit far above the neutral reference above, so a genuinely neutral face is quiet,
# while an obvious smile or open mouth is caught. Deliberately insensitive: a false "please
# retake" wastes a user's time, and the downstream validator is not relying on these.

SMILE_SCORE: Final[float] = 0.35
"""Max of mouthSmileLeft/Right above which we advise that the expression may not be neutral.
Neutral reference measured 0.004. Most specs require a neutral expression with mouth closed."""

JAW_OPEN_SCORE: Final[float] = 0.30
"""jawOpen above which we advise the mouth may be open. Neutral reference measured 0.037."""

EYE_CLOSED_SCORE: Final[float] = 0.55
"""Max of eyeBlinkLeft/Right above which we advise an eye may be closed. Neutral reference
measured 0.15 and 0.07. Set high because a partly-lidded eye is common and acceptable, while
every spec surveyed requires eyes open and visible."""

# --- Geometry sanity --------------------------------------------------------------------

MIN_IED_PIXELS: Final[float] = 90.0
"""Below this, the SOURCE image is too small to produce a compliant output at any crop.
This one is NOT our invention: ICAO's Portrait Quality technical report, Table 5, requires
IED >= 90 pixels and recommends >= 240 as best practice. Applied to the source because
cropping only ever reduces it and upscaling adds pixels without adding facial detail."""

MATTE_BORDER_TOUCH_FRACTION: Final[float] = 0.02
"""If the person matte occupies more than this fraction of the image's top row, we treat the
crown as truncated rather than measured — the head probably continues past the frame. Our own
heuristic; the alternative is silently reporting the image edge as the top of someone's head."""
