# Negative results

Approaches that were tried and failed, or that look attractive and are not usable. Recorded so
they are not retried. Cited from [README.md](README.md). Fresh as of 2026-09-04.

Each entry states what was observed, under what conditions, and what is *inference* rather than
evidence.

---

## MediaPipe 1.0.x aborts on macOS and fails on headless Linux

**Do not use mediapipe 1.0.x. Pin 0.10.x.**

`mediapipe==1.0.1`, `FaceLandmarker.create_from_options()` aborts during graph setup:

```
absl::log_internal::LogMessage::Flush()
-[DrishtiMetalHelper initWithCalculatorContext:]
mediapipe::api2::TensorsToDetectionsCalculator::Open()
mediapipe::CalculatorNode::OpenNode()
```

Observed 2026-09-04 on macOS 26.6.1, M4 Max, on **both** Python 3.14 (unsupported by the vendor;
classifiers list 3.9–3.12, but the wheel is `py3-none-macosx_11_0_arm64` with no `Requires-Python`
gate so pip installs it anyway) **and** Python 3.12.8 arm64 via `uv`. Setting
`BaseOptions.Delegate.CPU` does not avoid it — the Metal helper is constructed while opening the
calculator node regardless of the requested delegate.

Same version on Linux (Ubuntu, kernel 6.8, x86_64, headless) fails differently, at import:

```
OSError: libGLESv2.so.2: cannot open shared object file
```

**The Linux failure was a missing system library, not a bug.** After
`sudo apt install libgles2`, mediapipe **1.0.1 runs correctly on Linux** and produces values
identical to macOS 0.10.21 on the same image - chin y=2282, eye line y=1320, IED=492, pose
-0.6/1.7/1.7, to the digit. So the abort is specific to 1.0.x on macOS, and the version pin is a
platform workaround rather than a correctness concern: two versions on two architectures agree
exactly.

**Still inference, not established fact:** the macOS abort is *consistent with* 1.0.x requiring a
graphics stack during graph setup in a way 0.10.x does not, but we did not confirm that in
mediapipe's source. What is established is the reproduction above, and that 0.10.21 initialises GL
successfully on the same machine (`GL version: 2.1 (2.1 Metal - 90.5), renderer: Apple M4 Max`).

A search of the mediapipe issue tracker on 2026-09-04 found no report matching the
`DrishtiMetalHelper` signature. Adjacent open macOS/Metal issues exist (#5267 and others) but none
is this trace.

**Linux requirement:** any mediapipe version needs `libgles2` present
(`sudo apt install libgles2`). Required for any CI image.

---

## InsightFace `buffalo_l` — non-commercial weights, cannot ship

This was the first stack validated and it works well. It is nonetheless unusable here.

InsightFace's *code* is MIT. Its *pretrained models* are "available for non-commercial research
purposes only", stated in three places, including one that explicitly covers auto-downloaded
models. That is incompatible with this project's redistribution and commercial-use requirements.
There is no permissively licensed variant in the pack — `buffalo_s` and `buffalo_sc` sit under the
same model-zoo banner.

Sources: <https://github.com/deepinsight/insightface>,
<https://github.com/deepinsight/insightface/tree/master/model_zoo>,
<https://github.com/deepinsight/insightface/tree/master/python-package>

## dlib 68-landmark — same problem, different route

The iBUG 300-W annotations forbid commercial use, and dlib's author states the restriction reaches
the trained model at the dataset creator's request. Applies to both
`shape_predictor_68_face_landmarks.dat` and the `_GTX` variant.

Source: <https://github.com/davisking/dlib-models>

## 3DDFA_V2, SynergyNet, PIPNet, 6DRepNet, Hopenet, FSA-Net — no weights licence at all

Permissive code licences, but **none states a licence for the weights**, and most are trained on
300W-LP (derived from iBUG 300-W). Whether training-data terms propagate to model weights is an
unsettled legal question we are not qualified to resolve. The practical blocker is simpler: there
is no grant to rely on.

---

## Background segmentation: `u2net` and `isnet-general-use` erase light clothing

On a subject wearing a light tweed jacket, both models classified the jacket as background,
leaving a ghost-white torso with the shirt floating. `birefnet-general` retained the jacket
correctly. Observed 2026-09-04.

`alpha_matting=True` with aggressive thresholds made the matte **worse**, not better.

Separately, avoid `isnet-general-use` on licensing grounds regardless of quality: its Apache-2.0
covers "code and evaluation metric", pointedly not weights, with dataset terms in a separate PDF.

**Never call rembg with default model selection.** The current default is BRIA RMBG-2.0, which
requires a paid agreement for commercial use. Always pin the model explicitly.

---

## solvePnP from sparse landmarks cannot certify a pose tolerance

Tempting because it needs no extra model and no extra licence. Published mean absolute error for
landmark→PnP pose pipelines is 7.4–15.8° (Ruiz et al., CVPRW 2018), against tolerances of ±20°
yaw/roll and ±25° pitch — error between a third and half of the entire allowed band. The dlib row
in that benchmark shows 23.15° yaw MAE, larger than the whole tolerance.

**Important caveat on this citation:** those are benchmark MAEs on AFLW2000, not per-image
uncertainty bounds, and not measurements of any configuration we propose. They justify *not
building a compliance verdict on PnP*. They do not quantify our error.

Usable as an advisory "head appears turned" warning with uncertainty stated. Never as a verdict.

Source: <https://ar5iv.labs.arxiv.org/html/1710.00925>

---

## Two landmark models disagree on pose by more than half of ICAO's tolerance

Measured 2026-09-04 on one frontal portrait, same source image:

| | pitch | yaw | roll |
|---|---|---|---|
| MediaPipe 0.10.21 (transformation matrix) | −0.6° | 1.7° | 1.7° |
| InsightFace `buffalo_l` | −3.2° | 3.4° | −0.4° |

Up to 2.6° apart, against an ICAO tolerance of ±5°. The same two models agreed within **1 px** on
inter-eye distance and **4 px** on eye-line position for that image, so this is specific to pose,
not general disagreement.

This is a single image and does not establish either model's accuracy. It does establish that
pose cannot be treated as settled by whichever model happens to be installed. Pose stays advisory
until an acceptance gate against known angles passes.

---

## The wrong-channel error this project exists to prevent

Recorded because it is the founding example, and because it was made deliberately carefully.

Building a Chinese **digital** visa photo (354×472–420×560 px), a crop was sized to head height
28–33 mm and head width 15–22 mm. Those are the **paper** photo's rules. The digital spec sets no
head-height bound at all. Result: a face smaller than the digital template's face-width rule wants
— 219 px against a 191–219 px band, sitting exactly on the upper edge, and short of the band
entirely under the reading where those pixel figures scale with output size.

Rebuilt to the digital rules at the spec's own reference size, face width landed at 204 px,
mid-band.

No tool caught this. A person did, three hours later, while reading the source document again.
