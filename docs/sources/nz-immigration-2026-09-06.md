# New Zealand — Immigration New Zealand photo requirements, as retrieved 2026-09-06

Verbatim quotations from the official pages named below, fetched on that date; this file is provenance for the profile in src/visaphoto/profiles.py and is not a summary.

# INZ photo requirements — verbatim source report

**Retrieved 2026-09-06.** All quotes taken from raw HTML/PDF fetched today, not from a summarizer.

## Sources (and URL changes)

| Key | Page | URL |
|---|---|---|
| **A** | Acceptable photos for a visa or NZeTA | `https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/visa-and-nzeta-photos/` |
| **B** | Fixing errors when uploading a photo | `https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/fixing-errors-when-uploading-a-photo/` |
| **C** | File formats for uploading documents and photos | `https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/file-formats-for-uploading-documents-and-photos/` |
| **D** | PDF: *Taking acceptable visa photos — Technical requirements for professional photographers* (linked from A) | `https://www.immigration.govt.nz/assets/inz/documents/apply-for-a-visa/Taking-acceptable-visa-photos.pdf` |

The URL in your brief now **301s**: `/new-zealand-visas/preparing-a-visa-application/photographs-and-passport-photos` → HTTP 301. The older `/new-zealand-visas/apply-for-a-visa/tools-and-information/acceptable-photos` resolves (200) to **A**. **There is no separate NZeTA photo page** — the NZeTA landing page (`/visas/new-zealand-electronic-travel-authority-nzeta/`) links to A with "Make sure your photos are acceptable for an NZeTA." A covers both visa and NZeTA.

---

## 1. Pixel dimensions and aspect ratio

**A**, heading *Photo standards › Photos for online applications › Size and format the photo correctly* — states **only** aspect ratio in text:

> Your photo must be:
> - between 512 KB and 3.14 MB
> - taken in portrait mode with 3:4 aspect ratio
> - a JPG or JPEG file.

A states pixel dimensions **only inside the example image** (alt text "This photo shows acceptable visa photo dimensions."), which I downloaded and read. The image labels read: `900 pixels minimum` / `2250 pixels maximum` (width) and `1200 pixels minimum` / `3000 pixels maximum` (height).

**B**, heading *Online error messages › "The picture is not a passport style portrait of suitable file size or otherwise does not meet our requirements" › How to fix your photo* (identical text repeats under *"The picture must be in a passport portrait format"*):

> Your photo must be:
> - between 900 x 1200 and 2250 x 3000 pixels
> - between 500 KB and 3 MB, and
> - in portrait format.

**B**, heading *"The photo must be of sufficient resolution" › How to fix your photo*:

> Check your photo is between:
> - 900 x 1200 and 2250 x 3000 pixels, and
> - 500 KB and 3 MB.

**D**, section *1. Adjust camera settings*:

> • The photo must have dimensions between 900 x 1200 pixels and 2250 x 3000 pixels.

**D**, section *6. Image size of photos for online applications*:

> Save the image as a jpeg and make sure the file size is between 500kb and 3MB and have dimensions between 900 x 1200 pixels and 2250 x 3000 pixels.

Note 900×1200 and 2250×3000 are both exactly 3:4, so the ratio statement is consistent. **4:5 appears nowhere.**

## 2. File size limits — the conflict is live on both pages

Both figures exist today; neither page has been retired.

**A** (heading as §1 above):

> - between 512 KB and 3.14 MB

**B** (three separate places, quoted in §1):

> - between 500 KB and 3 MB, and

**D**:

> • The photo file size must be between 500KB and 3 MB

Separate, larger ceiling on **A**, heading *Using a professional photographer*:

> Make sure:
> - the photographer has our requirements
> - the photo file size is less than 10 MB.

## 3. File format, colour, DPI

**A** (heading as §1):

> - a JPG or JPEG file.

**C**, heading (H1) *File formats for uploading documents and photos*:

> All documents uploaded must be PDFs and all images must be JPEGs or JPGs.

**C**, heading *Photographs must be in JPG or JPEG format*:

> You need to upload a photo of yourself showing a full-front view of your face as part of your application. Visa photos have specific requirements such as no smiling and no hair covering your face.

**D**, *1. Adjust camera settings*:

> • set the camera to take colour photos
> • set the camera to save images as JPG (or JPEG) files
> • set the colour to sRGB (to match the colours that most video monitors and printers reproduce)

**PNG is not accepted.** **No DPI figure appears on A, B, or D** (grep for "dpi" returns 0 in all three).

## 4. Head size and position

**A**, heading *Position your face correctly*:

> Make sure:
> - your face covers between 70% and 80% of the image and is in the middle of the frame
> - you are looking straight at the camera with a neutral expression and your mouth is closed, and
> - your face is not turned to the side or on an angle.

**B**, heading *"The face image must not be too large or too small" › How to fix your photo*:

> Make sure:
> - your face takes up 70% to 80% of the frame
> - you have a clear gap around the head, and
> - your photo is between 900 x 1200 pixels and 2250 x 3000 pixels.

**D**, *5. Position the head and take the photo* — a different, more specific scheme:

> • the person's face is in the centre, of the frame
> • you can imagine a centre line going from the bottom of the image through the centre of the mouth and nose to the top of the image
> • the length of the head fills 75% of the frame (see A)
> • the width of the head fills 70% of the frame with equal space on both sides (see B)
> • the eyes are positioned in the top half of the frame, between points C and D
> • there is a light background showing around the entire head.

## 5. Prohibition on editing/altering — exact wording

**A**, top-of-page *Alert* callout (no heading; first block under H1 *Acceptable photos for a visa or NZeTA*):

> You cannot manipulate or digitally alter your photo using Artificial Intelligence (AI) or other digital editing tools. If your photo does not meet our standards your visa application or NZeTA request may be delayed or could be declined or refused.

**A**, heading *Photo standards*:

> Your photo must:
> - look like you
> - have been taken within the last 6 months
> - be a photo of you which is not edited or altered, and
> - not be a photo of a photo.

> Photos that are AI enhanced or altered do not meet our standards. If you use AI to edit your photos your visa application or NZeTA request will be delayed or could be declined.

**A**, heading *Do not edit or enhance the photo* — this is the passage carrying the background-replacement prohibition:

> The photo must be natural and unaltered.
>
> Do not use:
> - filters
> - beautification features
> - AI editing tools.
>
> This includes:
> - changing the colour, brightness, contrast or sharpness
> - cropping your head and shoulders to place it on a plain background
> - changing your facial features, for example, size, shape or colour of your eyes, nose, ears, mouth, cheekbones, or eyebrows
> - skin smoothing or face slimming
> - digitally removing objects from the photo, especially around the image of your face, for example, glasses, jewellery, headbands, hats or toys on or around the image.

> **Note**
> If your phone automatically filters or alters photos when you take them, turn this feature off when taking your visa or NZeTA photo.

Note the exact phrasing is **"cropping your head and shoulders to place it on a plain background"** — not "cutting out". It is listed as an instance of *editing/enhancing*, so background replacement is prohibited by this bullet.

## 6. Background, expression, glasses, head coverings, recency, selfies

**A**, *Use a plain background*:

> Objects in the background of your photo may prevent our system from recognising your face.
>
> The background of your photo must:
> - be neutral and plain, and
> - only show you and no other people or objects.
>
> Avoid wearing t-shirts with pictures on them, flowery or patterned backgrounds and clothing. Patterns can create technical issues with our system.

**B**, *"The photo must not be too dark or too bright"*: "your background is not too bright or too dark — light grey is often a good background colour, and". **D**, *2*: "in front of a plain, light-coloured (not white) background".

**Expression** — A, *Position your face correctly*: "you are looking straight at the camera with a neutral expression and your mouth is closed".

**Glasses** — A, *If you wear glasses*:

> You can wear prescription glasses.
>
> Make sure your glasses:
> - are clear and not tinted — no sunglasses
> - do not have heavy frames that cover your face, and
> - do not create a glare or reflection in the photo.
>
> If you are having issues with glasses, it may be best to remove them for your photo.

**Head coverings / visibility** — A, *Be clearly visible*:

> - Your hair must not cover your face or ears — the photo must show your ears unless you wear a scarf for religious or medical reasons.
> - Remove any head coverings (unless worn for religious or medical reasons).
> - If you wear a head covering for religious or medical reasons, your covering must not cover your mouth or the sides of your face.
> - Your eyes must be open.
> - The image must be in focus and not blurry.

**Recency** — A, *Photo standards*: "have been taken within the last 6 months".

**Selfies / at home** — A, *Using selfies*:

> It can be difficult to take a selfie that meets our photo requirements. Where possible, we recommend that you have someone else take your photo, to our requirements.
>
> You can only use a selfie photo if you use the mobile app to apply for an NZeTA.
>
> If you are applying in the mobile app and you only have the option of submitting a selfie, make sure:
> - your arm is stretched out as far as possible to create space between the phone and your face
> - you hold the phone at the same height as your eyebrows
> - the light source is behind the phone or camera.

Home photos are not prohibited; A gives home-setup distances under *Use good lighting*: "stand 0.5 metres from the background, and" / "the photographer must be 1.5 metres in front of you when they take the photo." A also says, under *Using a professional photographer*: "We are more likely to accept your photo if you use a professional photographer."

## 7. Printed photo (35 × 45 mm)

**A**, *Photos for paper-based visa applications*:

> The photo you submit with a paper application must be 35 mm wide and 45 mm high.
>
> More instructions are on the paper application forms.
>
> **Note**
> You can only apply for an NZeTA online.

**No head-height band in mm is stated anywhere on A, B, C, or D.** Do not encode one.

---

## Contradictions between INZ pages

1. **File size: 512 KB – 3.14 MB (A) vs 500 KB – 3 MB (B and D).** Both live today. A is the requirements page; B is the page the applicant reaches after the upload validator rejects the file, and D is INZ's own photographer spec. Two of three sources say 500 KB – 3 MB. Safest encoding: **min 512 KB, max 3 MB** (intersection).
2. **Pixel dimensions absent from A's body text.** A states only "3:4 aspect ratio"; the 900×1200–2250×3000 range appears on A only inside a `.png` image. B and D state it in text.
3. **Head size: A/B say the *face* is 70–80% of the image/frame; D says the *head* length fills 75% and head width fills 70%.** Different subject (face vs head) and different structure (band vs two fixed figures). D is aimed at professional photographers.
4. **Wording drift A vs B:** "your face covers between 70% and 80% of the image" vs "your face takes up 70% to 80% of the frame". Same numbers; B adds "you have a clear gap around the head", which A does not state for the online photo.
5. **Background colour: A says "neutral and plain" (no colour); B suggests "light grey is often a good background colour"; D requires "plain, light-coloured (not white)".** A does not forbid white; D does.
6. **Two file-size ceilings on A itself:** 3.14 MB under *Size and format the photo correctly*, and "less than 10 MB" under *Using a professional photographer*.
7. **Stale link in an INZ PDF:** the visitor visa guide (`/assets/inz/documents/forms-and-guides/visitor-visa-guide-english-final.pdf`) points to `www.immigration.govt.nz/new-zealand-visas/apply-for-a-visa/tools-and-information/acceptable-photos`, which now redirects to A.

## Facts NOT found on any page read (do not guess)

- **DPI / PPI** — no statement on A, B, C, or D.
- **PNG** — never listed as accepted; only JPG/JPEG.
- **4:5 aspect ratio** — appears nowhere.
- **Eye position as a measurable rule for online photos** — only D's qualitative "the eyes are positioned in the top half of the frame, between points C and D" (points C/D are defined only by a figure in the PDF; no numeric value).
- **Space above the head in mm or %** — not stated. Nearest are D's "there is a light background showing around the entire head" and B's "you have a clear gap around the head".
- **Head-height band in mm for the 35 × 45 mm printed photo** — not stated by INZ. (A web search surfaced 29.25–33.75 mm and eye-height 22.5–31.5 mm, but every one of those hits was a third-party passport-photo vendor, not immigration.govt.nz. Do not encode them as INZ rules.)
- **Explicit "must be colour / not black and white" for online photos** — only D's camera instruction "set the camera to take colour photos"; A never states it.
- **Any NZeTA-specific numeric spec distinct from visa specs** — none; A governs both, and the only NZeTA-specific rule is the selfie allowance in the mobile app.

Sources: [Acceptable photos for a visa or NZeTA](https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/visa-and-nzeta-photos/) · [Fixing errors when uploading a photo](https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/fixing-errors-when-uploading-a-photo/) · [File formats for uploading documents and photos](https://www.immigration.govt.nz/process-to-apply/applying-for-a-visa/applying-online/uploading-documents-and-photos/file-formats-for-uploading-documents-and-photos/) · [Taking acceptable visa photos (PDF)](https://www.immigration.govt.nz/assets/inz/documents/apply-for-a-visa/Taking-acceptable-visa-photos.pdf) · [NZeTA landing page](https://www.immigration.govt.nz/visas/new-zealand-electronic-travel-authority-nzeta/)
