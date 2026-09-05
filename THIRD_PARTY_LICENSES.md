# Third-party licences

Cited from [README.md](README.md). Fresh as of 2026-09-04.

**Code licences and model-weight licences are stated separately throughout.** They frequently
differ, and permissive code with restricted weights is the most common trap in this space — it is
why one otherwise-excellent library is rejected below. No model is used here without an
affirmative licence grant covering *the weights*.

Model artifacts are not committed to this repository. They are fetched at install time and pinned
by revision and checksum so that a measurement is reproducible.

## In use

| Component | Code licence | **Weights licence** | Source |
|---|---|---|---|
| MediaPipe (Face Landmarker) | Apache-2.0 | **Apache-2.0** | [repo](https://github.com/google-ai-edge/mediapipe) · [FaceMesh V2 model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf) · [BlazeFace model card](https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20(Short%20Range).pdf) |
| rembg | MIT | n/a (fetches models) | [repo](https://github.com/danielgatis/rembg) |
| BiRefNet | MIT | **MIT** | [repo](https://github.com/ZhengPeng7/BiRefNet) · [weights](https://huggingface.co/ZhengPeng7/BiRefNet) |

MediaPipe's weights licence is stated on Google's own per-model cards, not inferred from the code
repository. Apache-2.0 additionally carries a patent grant, which matters for a face-processing
tool.

Attribution obligations we take on: reproduce the Apache-2.0 text and preserve any `NOTICE`
contents for MediaPipe; reproduce the MIT text and copyright notices for BiRefNet (Peng Zheng) and
rembg (Daniel Gatis). None of these are copyleft, so none constrains this project's own licence.

**Operational requirement:** rembg must always be called with an explicitly pinned model. Its
current default is BRIA RMBG-2.0, whose weights require a paid agreement for commercial use.
Accepting rembg's default would silently pull in a non-free model.

## Approved fallbacks

| Component | Code licence | **Weights licence** | Source |
|---|---|---|---|
| OpenSeeFace | BSD 2-clause | **BSD 2-clause, explicitly covering models** | [repo](https://github.com/emilianavt/OpenSeeFace) |
| MODNet | Apache-2.0 | **Apache-2.0** ("code, models, and demos") | [repo](https://github.com/ZHKKKe/MODNet) |

If OpenSeeFace is adopted, its `Licenses` folder must be redistributed alongside it, as its README
requires.

## Rejected

Recorded so the decision is not silently revisited. Full reasoning in
[NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md).

| Component | Why not |
|---|---|
| InsightFace (`buffalo_l` and all model-zoo packs) | MIT code, but weights are "non-commercial research purposes only" — including auto-downloaded ones. Incompatible with this project's redistribution and commercial-use requirements. |
| dlib 68-landmark predictors | iBUG 300-W annotations exclude commercial use; dlib's author states the restriction reaches the trained model. |
| 3DDFA_V2, SynergyNet, PIPNet, 6DRepNet, Hopenet, FSA-Net | Permissive code, **no stated weights licence at all**; most trained on 300W-LP. No grant to rely on. |
| BRIA RMBG-2.0 (rembg's default) | Requires a paid agreement for commercial use. |
| `isnet-general-use` | Apache-2.0 covers "code and evaluation metric", pointedly not weights; dataset terms are separate. |
| Basel Face Model, Surrey Face Model (`eos`) | Non-commercial. Where a canonical 3D face model is needed, use MediaPipe's `canonical_face_model.obj` (Apache-2.0). |

## Under evaluation

**OFIQ** ([BSI-OFIQ/OFIQ-Project](https://github.com/BSI-OFIQ/OFIQ-Project)) — the ISO/IEC 29794-5
reference implementation, and the right long-term answer for image-quality scoring. Deferred past
v1. Its GitHub licence classifies as `NOASSERTION` while BSI's own overview deck describes a
liberal, commercial-use-permitting licence. **Verify `LICENSE.md` and its bundled third-party model
terms before taking any dependency on it.**
