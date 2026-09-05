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

SMILE_SCORE: Final[float] = 0.13
"""Max of mouthSmileLeft/Right above which we advise the expression may not be neutral.

Calibrated, not guessed. Across 18 posed photographs the two classes separate cleanly:

    not smiling (9 photos)   0.000 - 0.088   highest was a bared-teeth grimace
    smiling     (8 photos)   0.179 - 0.912   lowest was a subtle closed-lip smile

0.13 sits in the empty gap between them. The previous value of 0.35 missed three genuine
smiles, including one at 0.337 that was plainly visible."""

JAW_OPEN_SCORE: Final[float] = 0.30
"""jawOpen above which we advise the mouth may be open. Neutral reference measured 0.037."""

EYE_CLOSED_SCORE: Final[float] = 0.42
"""Max of eyeBlinkLeft/Right above which we advise an eye may be closed.

Calibrated across the same 18 photographs:

    eyes open   (15 photos)  0.020 - 0.344   highest was a head-tilted-back shot
    eyes shut   (2 photos)   0.526 - 0.793

0.42 sits between. The previous 0.55 missed a photo with both eyes squeezed shut (0.526).

KNOWN LIMITATION - a one-eyed wink is NOT caught by this signal. On the one wink in the set,
eyeBlink scored 0.182/0.211 while eyeSquint scored 0.451/0.736: MediaPipe classifies a hard
wink as a squint, not a blink. eyeSquint cannot be used directly, because it reads 0.43-0.47
on a fully neutral face. Left-right squint asymmetry does separate it (0.285 for the wink
against 0.043 for neutral), but one example is not enough to set a threshold on. See
ROADMAP.md."""

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

HEAD_WIDTH_BAND_BELOW_EYES: Final[float] = 0.5
"""How far from the eye line towards the chin to keep measuring head width, as a fraction.

Our own heuristic, and it exists because bounding the band at the chin is not enough. Measured
row widths on the reference photo, crown y=493 to chin y=2278:

    y= 623  732      y=1403 1078  <- true peak, ear/temple level
    y=1143 1076      y=2053  844  <- jaw, narrowing
    y=1273 1074      y=2277 1236  <- collar and shoulders have entered the frame

A head is widest at the ears, well above the chin, and the torso enters the silhouette before
the chin row is reached. Taking the maximum over crown-to-chin therefore reports shoulder
width. Stopping halfway between the eye line and the chin captures the real peak (1078) and
stays clear of the collar.
"""
